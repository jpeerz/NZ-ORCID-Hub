# -*- coding: utf-8 -*-
"""Various utilities."""

import json
import logging
import os
from datetime import datetime, timedelta
from itertools import filterfalse, groupby
from urllib.parse import quote, urlencode, urlparse

import emails
import flask
import requests
from flask import request, url_for
from flask_login import current_user
from html2text import html2text
from itsdangerous import BadSignature, TimedJSONWebSignatureSerializer
from jinja2 import Template
from peewee import JOIN

from . import app, orcid_client, rq
from .models import (AFFILIATION_TYPES, Affiliation, AffiliationRecord, FundingInvitees,
                     FundingRecord, OrcidToken, Organisation, PartialDate, PeerReviewExternalId,
                     PeerReviewInvitee, PeerReviewRecord, Role, Task, Url, User, UserInvitation,
                     UserOrg, WorkInvitees, WorkRecord, get_val)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

EDU_CODES = {"student", "edu"}
EMP_CODES = {"faculty", "staff", "emp"}

ENV = app.config.get("ENV")
EXTERNAL_SP = app.config.get("EXTERNAL_SP")


def get_next_url():
    """Retrieve and sanitize next/return URL."""
    _next = request.args.get("next") or request.args.get("_next") or request.args.get("url")

    if _next and ("orcidhub.org.nz" in _next or _next.startswith("/") or "127.0" in _next
                  or "c9users.io" in _next):
        return _next
    return None


def is_valid_url(url):
    """Validate URL (expexted to have a path)."""
    try:
        result = urlparse(url)
        return result.scheme and result.netloc and (result.path or result.path == '')
    except:
        return False


def send_email(template,
               recipient,
               cc_email=None,
               sender=(app.config.get("APP_NAME"), app.config.get("MAIL_DEFAULT_SENDER")),
               reply_to=None,
               subject=None,
               base=None,
               logo=None,
               org=None,
               **kwargs):
    """Send an email, acquiring its payload by rendering a jinja2 template.

    :type template: :class:`str`
    :param subject: the subject of the email
    :param base: the base template of the email messagess
    :param template: name of the template file in ``templates/emails`` to use
    :type recipient: :class:`tuple` (:class:`str`, :class:`str`)
    :param recipient: 'To' (name, email)
    :type sender: :class:`tuple` (:class:`str`, :class:`str`)
    :param sender: 'From' (name, email)
    :param org: organisation on which behalf the email is sent
    * `recipient` and `sender` are made available to the template as variables
    * In any email tuple, name may be ``None``
    * The subject is retrieved from a sufficiently-global template variable;
      typically set by placing something like
      ``{% set subject = "My Subject" %}``
      at the top of the template used (it may be inside some blocks
      (if, elif, ...) but not others (rewrap, block, ...).
      If it's not present, it defaults to "My Subject".
    * With regards to line lengths: :class:`email.mime.text.MIMEText` will
      (at least, in 2.7) encode the body of the text in base64 before sending
      it, text-wrapping the base64 data. You will therefore not have any
      problems with SMTP line length restrictions, and any concern to line
      lengths is purely aesthetic or to be nice to the MUA.
      :class:`RewrapExtension` may be used to wrap blocks of text nicely.
      Note that ``{{ variables }}`` in manually wrapped text can cause
      problems!
    """
    if not org and current_user and not current_user.is_anonymous:
        org = current_user.organisation
    jinja_env = flask.current_app.jinja_env

    if logo is None:
        if org and org.logo:
            logo = url_for("logo_image", token=org.logo.token, _external=True)
        else:
            logo = url_for("static", filename="images/banner-small.png", _external=True)

    if not base and org:
        if org.email_template_enabled and org.email_template:
            base = org.email_template

    if not base:
        base = app.config.get("DEFAULT_EMAIL_TEMPLATE")

    jinja_env = jinja_env.overlay(autoescape=False)

    def _jinja2_email(name, email):
        if name is None:
            hint = 'name was not set for email {0}'.format(email)
            name = jinja_env.undefined(name='name', hint=hint)
        return {"name": name, "email": email}

    if '\n' not in template and template.endswith(".html"):
        template = jinja_env.get_template(template)
    else:
        template = Template(template)

    kwargs["sender"] = _jinja2_email(*sender)
    kwargs["recipient"] = _jinja2_email(*recipient)
    if subject is not None:
        kwargs["subject"] = subject
    if reply_to is None:
        reply_to = sender

    rendered = template.make_module(vars=kwargs)
    if subject is None:
        subject = getattr(rendered, "subject", "Welcome to the NZ ORCID Hub")

    html_msg = base.format(
        EMAIL=kwargs["recipient"]["email"],
        SUBJECT=subject,
        MESSAGE=str(rendered),
        LOGO=logo,
        BASE_URL=url_for("index", _external=True)[:-1],
        INCLUDED_URL=kwargs.get("invitation_url", '') or kwargs.get("include_url", ''))

    plain_msg = html2text(html_msg)

    msg = emails.html(
        subject=subject,
        mail_from=(app.config.get("APP_NAME", "ORCID Hub"), app.config.get("MAIL_DEFAULT_SENDER")),
        html=html_msg,
        text=plain_msg)
    dkip_key_path = app.config["DKIP_KEY_PATH"]
    if os.path.exists(dkip_key_path):
        msg.dkim(key=open(dkip_key_path), domain="orcidhub.org.nz", selector="default")
    if cc_email:
        msg.cc.append(cc_email)
    msg.set_headers({"reply-to": reply_to})
    msg.mail_to.append(recipient)
    msg.send(smtp=dict(host=app.config["MAIL_SERVER"], port=app.config["MAIL_PORT"]))


def generate_confirmation_token(*args, expiration=1300000, **kwargs):
    """Generate Organisation registration confirmation token.

    Invitation Token Expiry for Admins is 15 days, whereas for researchers the token expiry is of 30 days.
    """
    serializer = TimedJSONWebSignatureSerializer(app.config["SECRET_KEY"], expires_in=expiration)
    if len(kwargs) == 0:
        return serializer.dumps(args[0] if len(args) == 1 else args)
    else:
        return serializer.dumps(kwargs.values()[0] if len(kwargs) == 1 else kwargs)


def confirm_token(token, unsafe=False):
    """Genearate confirmaatin token."""
    serializer = TimedJSONWebSignatureSerializer(app.config["SECRET_KEY"])
    if unsafe:
        data = serializer.loads_unsafe(token)
    else:
        try:
            data = serializer.loads(token, salt=app.config["SALT"])
        except BadSignature:  # try again w/o the global salt
            data = serializer.loads(token, salt=None)
    return data


def append_qs(url, **qs):
    """Append new query strings to an arbitraty URL."""
    return url + ('&' if urlparse(url).query else '?') + urlencode(qs, doseq=True)


def track_event(category, action, label=None, value=0):
    """Track application events with Google Analytics."""
    ga_tracking_id = app.config.get("GA_TRACKING_ID")
    if not ga_tracking_id:
        return

    data = {
        "v": "1",  # API Version.
        "tid": ga_tracking_id,  # Tracking ID / Property ID.
        # Anonymous Client Identifier. Ideally, this should be a UUID that
        # is associated with particular user, device, or browser instance.
        "cid": current_user.uuid,
        "t": "event",  # Event hit type.
        "ec": category,  # Event category.
        "ea": action,  # Event action.
        "el": label,  # Event label.
        "ev": value,  # Event value, must be an integer
    }

    response = requests.post("http://www.google-analytics.com/collect", data=data)

    # If the request fails, this will raise a RequestException. Depending
    # on your application's needs, this may be a non-error and can be caught
    # by the caller.
    response.raise_for_status()
    # Returning response only for test, but can be used in application for some other reasons
    return response


def set_server_name():
    """Set the server name for batch processes."""
    if not app.config.get("SERVER_NAME"):
        if EXTERNAL_SP:
            app.config["SERVER_NAME"] = "127.0.0.1:5000"
        else:
            app.config[
                "SERVER_NAME"] = "orcidhub.org.nz" if ENV == "prod" else ENV + ".orcidhub.org.nz"


def send_work_funding_peer_review_invitation(inviter, org, email, first_name=None, last_name=None, task_id=None,
                                             invitation_template=None, token_expiry_in_sec=1300000, **kwargs):
    """Send a work, funding or peer review invitation to join ORCID Hub logging in via ORCID."""
    try:
        logger.info(f"*** Sending an invitation to '{first_name} <{email}>' "
                    f"submitted by {inviter} of {org}")

        email = email.lower()
        user, user_created = User.get_or_create(email=email)
        if user_created:
            user.created_by = inviter.id
        else:
            user.updated_by = inviter.id

        if first_name and not user.first_name:
            user.first_name = first_name

        if last_name and not user.last_name:
            user.last_name = last_name

        user.organisation = org
        user.roles |= Role.RESEARCHER
        token = generate_confirmation_token(expiration=token_expiry_in_sec, email=email, org=org.name)
        with app.app_context():
            url = flask.url_for('orcid_login', invitation_token=token, _external=True)
            invitation_url = flask.url_for(
                "short_url", short_id=Url.shorten(url).short_id, _external=True)
            send_email(
                invitation_template,
                recipient=(user.organisation.name, user.email),
                reply_to=(inviter.name, inviter.email),
                invitation_url=invitation_url,
                org_name=user.organisation.name,
                org=org,
                user=user)

        user.save()

        user_org, user_org_created = UserOrg.get_or_create(user=user, org=org)
        if user_org_created:
            user_org.created_by = inviter.id
        else:
            user_org.updated_by = inviter.id
        user_org.affiliations = 0
        user_org.save()

        ui = UserInvitation.create(
            task_id=task_id,
            invitee_id=user.id,
            inviter_id=inviter.id,
            org=org,
            email=email,
            first_name=first_name,
            last_name=last_name,
            affiliations=0,
            organisation=org.name,
            disambiguated_id=org.disambiguated_id,
            disambiguation_source=org.disambiguation_source,
            token=token)

        return ui

    except Exception as ex:
        logger.error(f"Exception occured while sending mails {ex}")
        raise ex


def create_or_update_work(user, org_id, records, *args, **kwargs):
    """Create or update work record of a user."""
    records = list(unique_everseen(records, key=lambda t: t.work_record.id))
    org = Organisation.get(id=org_id)
    client_id = org.orcid_client_id
    api = orcid_client.MemberAPI(org, user)

    profile_record = api.get_record()

    if profile_record:
        activities = profile_record.get("activities-summary")

        def is_org_rec(rec):
            return (rec.get("source").get("source-client-id")
                    and rec.get("source").get("source-client-id").get("path") == client_id)

        works = []

        for r in activities.get("works").get("group"):
            ws = r.get("work-summary")[0]
            if is_org_rec(ws):
                works.append(ws)

        taken_put_codes = {
            r.work_record.work_invitees.put_code
            for r in records if r.work_record.work_invitees.put_code
        }

        def match_put_code(records, work_record, work_invitees):
            """Match and assign put-code to a single work record and the existing ORCID records."""
            if work_invitees.put_code:
                return
            for r in records:
                put_code = r.get("put-code")
                if put_code in taken_put_codes:
                    continue

                if ((r.get("title") is None and r.get("title").get("title") is None
                     and r.get("title").get("title").get("value") is None and r.get("type") is None)
                        or (r.get("title").get("title").get("value") == work_record.title
                            and r.get("type") == work_record.type)):
                    work_invitees.put_code = put_code
                    work_invitees.save()
                    taken_put_codes.add(put_code)
                    app.logger.debug(
                        f"put-code {put_code} was asigned to the work record "
                        f"(ID: {work_record.id}, Task ID: {work_record.task_id})")
                    break

        for task_by_user in records:
            wr = task_by_user.work_record
            wi = task_by_user.work_record.work_invitees
            match_put_code(works, wr, wi)

        for task_by_user in records:
            wi = task_by_user.work_record.work_invitees

            try:
                put_code, orcid, created = api.create_or_update_work(task_by_user)
                if created:
                    wi.add_status_line(f"Work record was created.")
                else:
                    wi.add_status_line(f"Work record was updated.")
                wi.orcid = orcid
                wi.put_code = put_code

            except Exception as ex:
                logger.exception(f"For {user} encountered exception")
                exception_msg = ""
                if ex and ex.body:
                    exception_msg = json.loads(ex.body)
                wi.add_status_line(f"Exception occured processing the record: {exception_msg}.")
                wr.add_status_line(
                    f"Error processing record. Fix and reset to enable this record to be processed: {exception_msg}."
                )

            finally:
                wi.processed_at = datetime.utcnow()
                wr.save()
                wi.save()
    else:
        # TODO: Invitation resend in case user revokes organisation permissions
        app.logger.debug(f"Should resend an invite to the researcher asking for permissions")
        return


def create_or_update_peer_review(user, org_id, records, *args, **kwargs):
    """Create or update peer review record of a user."""
    records = list(unique_everseen(records, key=lambda t: t.peer_review_record.id))
    org = Organisation.get(id=org_id)
    client_id = org.orcid_client_id
    api = orcid_client.MemberAPI(org, user)

    profile_record = api.get_record()

    if profile_record:
        activities = profile_record.get("activities-summary")

        def is_org_rec(rec):
            return (rec.get("source").get("source-client-id")
                    and rec.get("source").get("source-client-id").get("path") == client_id)

        peer_reviews = []

        for r in activities.get("peer-reviews").get("group"):
            peer_review_summary = r.get("peer-review-summary")
            for ps in peer_review_summary:
                if is_org_rec(ps):
                    peer_reviews.append(ps)

        taken_put_codes = {
            r.peer_review_record.peer_review_invitee.put_code
            for r in records if r.peer_review_record.peer_review_invitee.put_code
        }

        def match_put_code(records, peer_review_record, peer_review_invitee, taken_external_id_values):
            """Match and assign put-code to a single peer review record and the existing ORCID records."""
            if peer_review_invitee.put_code:
                return
            for r in records:
                put_code = r.get("put-code")

                external_id_value = r.get("external-ids").get("external-id")[0].get("external-id-value") if r.get(
                    "external-ids") and r.get("external-ids").get("external-id") and r.get("external-ids").get(
                    "external-id")[0].get("external-id-value") else None

                if put_code in taken_put_codes:
                    continue

                if (r.get("review-group-id") and r.get("review-group-id") == peer_review_record.review_group_id and
                            external_id_value in taken_external_id_values):     # noqa: E127
                    peer_review_invitee.put_code = put_code
                    peer_review_invitee.save()
                    taken_put_codes.add(put_code)
                    app.logger.debug(
                        f"put-code {put_code} was asigned to the peer review record "
                        f"(ID: {peer_review_record.id}, Task ID: {peer_review_record.task_id})")
                    break

        for task_by_user in records:
            pr = task_by_user.peer_review_record
            pi = pr.peer_review_invitee

            external_ids = PeerReviewExternalId.select().where(PeerReviewExternalId.peer_review_record_id == pr.id)
            taken_external_id_values = {ei.value for ei in external_ids if ei.value}
            match_put_code(peer_reviews, pr, pi, taken_external_id_values)

        for task_by_user in records:
            pr = task_by_user.peer_review_record
            pi = pr.peer_review_invitee

            try:
                put_code, orcid, created = api.create_or_update_peer_review(task_by_user)
                if created:
                    pi.add_status_line(f"Peer review record was created.")
                else:
                    pi.add_status_line(f"Peer review record was updated.")
                pi.orcid = orcid
                pi.put_code = put_code

            except Exception as ex:
                logger.exception(f"For {user} encountered exception")
                exception_msg = ""
                if ex and ex.body:
                    exception_msg = json.loads(ex.body)
                pi.add_status_line(f"Exception occured processing the record: {exception_msg}.")
                pr.add_status_line(
                    f"Error processing record. Fix and reset to enable this record to be processed: {exception_msg}."
                )

            finally:
                pi.processed_at = datetime.utcnow()
                pr.save()
                pi.save()
    else:
        # TODO: Invitation resend in case user revokes organisation permissions
        app.logger.debug(f"Should resend an invite to the researcher asking for permissions")
        return


def create_or_update_funding(user, org_id, records, *args, **kwargs):
    """Create or update funding record of a user."""
    records = list(unique_everseen(records, key=lambda t: t.funding_record.id))
    org = Organisation.get(id=org_id)
    client_id = org.orcid_client_id
    api = orcid_client.MemberAPI(org, user)

    profile_record = api.get_record()

    if profile_record:
        activities = profile_record.get("activities-summary")

        def is_org_rec(rec):
            return (rec.get("source").get("source-client-id")
                    and rec.get("source").get("source-client-id").get("path") == client_id)

        fundings = []

        for r in activities.get("fundings").get("group"):
            fs = r.get("funding-summary")[0]
            if is_org_rec(fs):
                fundings.append(fs)

        taken_put_codes = {
            r.funding_record.funding_invitees.put_code
            for r in records if r.funding_record.funding_invitees.put_code
        }

        def match_put_code(records, funding_record, funding_invitees):
            """Match and asign put-code to a single funding record and the existing ORCID records."""
            if funding_invitees.put_code:
                return
            for r in records:
                put_code = r.get("put-code")
                if put_code in taken_put_codes:
                    continue

                if ((r.get("title") is None and r.get("title").get("title") is None
                     and r.get("title").get("title").get("value") is None and r.get("type") is None
                     and r.get("organization") is None
                     and r.get("organization").get("name") is None)
                        or (r.get("title").get("title").get("value") == funding_record.title
                            and r.get("type") == funding_record.type
                            and r.get("organization").get("name") == funding_record.org_name)):
                    funding_invitees.put_code = put_code
                    funding_invitees.save()
                    taken_put_codes.add(put_code)
                    app.logger.debug(
                        f"put-code {put_code} was asigned to the funding record "
                        f"(ID: {funding_record.id}, Task ID: {funding_record.task_id})")
                    break

        for task_by_user in records:
            fr = task_by_user.funding_record
            fi = task_by_user.funding_record.funding_invitees
            match_put_code(fundings, fr, fi)

        for task_by_user in records:
            fi = task_by_user.funding_record.funding_invitees

            try:
                put_code, orcid, created = api.create_or_update_funding(task_by_user)
                if created:
                    fi.add_status_line(f"Funding record was created.")
                else:
                    fi.add_status_line(f"Funding record was updated.")
                fi.orcid = orcid
                fi.put_code = put_code

            except Exception as ex:
                logger.exception(f"For {user} encountered exception")
                exception_msg = ""
                if ex and ex.body:
                    exception_msg = json.loads(ex.body)
                fi.add_status_line(f"Exception occured processing the record: {exception_msg}.")
                fr.add_status_line(
                    f"Error processing record. Fix and reset to enable this record to be processed: {exception_msg}."
                )

            finally:
                fi.processed_at = datetime.utcnow()
                fr.save()
                fi.save()
    else:
        # TODO: Invitation resend in case user revokes organisation permissions
        app.logger.debug(f"Should resend an invite to the researcher asking for permissions")
        return


@rq.job(timeout=300)
def send_user_invitation(inviter,
                         org,
                         email,
                         first_name,
                         last_name,
                         affiliation_types=None,
                         orcid=None,
                         department=None,
                         organisation=None,
                         city=None,
                         state=None,
                         country=None,
                         course_or_role=None,
                         start_date=None,
                         end_date=None,
                         affiliations=None,
                         disambiguated_id=None,
                         disambiguation_source=None,
                         task_id=None,
                         cc_email=None,
                         token_expiry_in_sec=1300000,
                         **kwargs):
    """Send an invitation to join ORCID Hub logging in via ORCID."""
    try:
        if isinstance(inviter, int):
            inviter = User.get(id=inviter)
        if isinstance(org, int):
            org = Organisation.get(id=org)
        if isinstance(start_date, list):
            start_date = PartialDate(*start_date)
        if isinstance(end_date, list):
            end_date = PartialDate(*end_date)
        set_server_name()
        logger.info(f"*** Sending an invitation to '{first_name} {last_name} <{email}>' "
                    f"submitted by {inviter} of {org} for affiliations: {affiliation_types}")

        email = email.lower()
        user, user_created = User.get_or_create(email=email)
        if user_created:
            user.first_name = first_name
            user.last_name = last_name
        user.organisation = org
        user.roles |= Role.RESEARCHER
        token = generate_confirmation_token(expiration=token_expiry_in_sec, email=email, org=org.name)
        with app.app_context():
            url = flask.url_for('orcid_login', invitation_token=token, _external=True)
            invitation_url = flask.url_for(
                "short_url", short_id=Url.shorten(url).short_id, _external=True)
            send_email(
                "email/researcher_invitation.html",
                recipient=(user.organisation.name, user.email),
                reply_to=(inviter.name, inviter.email),
                cc_email=cc_email,
                invitation_url=invitation_url,
                org_name=user.organisation.name,
                org=org,
                user=user)

        user.save()

        user_org, user_org_created = UserOrg.get_or_create(user=user, org=org)
        if user_org_created:
            user_org.created_by = inviter.id
        else:
            user_org.updated_by = inviter.id

        if affiliations is None and affiliation_types:
            affiliations = 0
            if affiliation_types & {"faculty", "staff"}:
                affiliations = Affiliation.EMP
            if affiliation_types & {"student", "alum"}:
                affiliations |= Affiliation.EDU
        user_org.affiliations = affiliations

        user_org.save()
        ui = UserInvitation.create(
            task_id=task_id,
            invitee_id=user.id,
            inviter_id=inviter.id,
            org=org,
            email=email,
            first_name=first_name,
            last_name=last_name,
            orcid=orcid,
            department=department,
            organisation=organisation,
            city=city,
            state=state,
            country=country,
            course_or_role=course_or_role,
            start_date=start_date,
            end_date=end_date,
            affiliations=affiliations,
            disambiguated_id=disambiguated_id,
            disambiguation_source=disambiguation_source,
            token=token)

        status = "The invitation sent at " + datetime.utcnow().isoformat(timespec="seconds")
        (AffiliationRecord.update(status=AffiliationRecord.status + "\n" + status).where(
            AffiliationRecord.status.is_null(False), AffiliationRecord.email == email).execute())
        (AffiliationRecord.update(status=status).where(AffiliationRecord.status.is_null(),
                                                       AffiliationRecord.email == email).execute())
        return ui.id

    except Exception as ex:
        logger.exception(f"Exception occured while sending mails {ex}")
        raise


def unique_everseen(iterable, key=None):
    """List unique elements, preserving order. Remember all elements ever seen.

    The snippet is taken form https://docs.python.org/3.6/library/itertools.html#itertools-recipes
    >>> unique_everseen('AAAABBBCCDAABBB')
    A B C D
    >>> unique_everseen('ABBCcAD', str.lower)
    A B C D
    """
    seen = set()
    seen_add = seen.add
    if key is None:
        for element in filterfalse(seen.__contains__, iterable):
            seen_add(element)
            yield element
    else:
        for element in iterable:
            k = key(element)
            if k not in seen:
                seen_add(k)
                yield element


def create_or_update_affiliations(user, org_id, records, *args, **kwargs):
    """Create or update affiliation record of a user.

    1. Retries user edurcation and employment surramy from ORCID;
    2. Match the recodrs with the summary;
    3. If there is match update the record;
    4. If no match create a new one.
    """
    records = list(unique_everseen(records, key=lambda t: t.affiliation_record.id))
    org = Organisation.get(id=org_id)
    client_id = org.orcid_client_id
    api = orcid_client.MemberAPI(org, user)
    profile_record = api.get_record()
    if profile_record:
        activities = profile_record.get("activities-summary")

        def is_org_rec(rec):
            return (rec.get("source").get("source-client-id")
                    and rec.get("source").get("source-client-id").get("path") == client_id)

        employments = [
            r for r in (activities.get("employments").get("employment-summary")) if is_org_rec(r)
        ]
        educations = [
            r for r in (activities.get("educations").get("education-summary")) if is_org_rec(r)
        ]

        taken_put_codes = {
            r.affiliation_record.put_code
            for r in records if r.affiliation_record.put_code
        }

        def match_put_code(records, affiliation_record):
            """Match and asign put-code to a single affiliation record and the existing ORCID records."""
            for r in records:
                put_code = r.get("put-code")
                start_date = affiliation_record.start_date.as_orcid_dict() if affiliation_record.start_date else None
                end_date = affiliation_record.end_date.as_orcid_dict() if affiliation_record.end_date else None

                if (r.get("start-date") == start_date and r.get(
                    "end-date") == end_date and r.get(
                    "department-name") == affiliation_record.department
                    and r.get("role-title") == affiliation_record.role
                    and get_val(r, "organization", "name") == affiliation_record.organisation
                    and get_val(r, "organization", "address", "city") == affiliation_record.city
                    and get_val(r, "organization", "address", "region") == affiliation_record.state
                    and get_val(r, "organization", "address", "country") == affiliation_record.country
                    and get_val(r, "organization", "disambiguated-organization",
                                "disambiguated-organization-identifier") == affiliation_record.disambiguated_id
                    and get_val(r, "organization", "disambiguated-organization",
                                "disambiguation-source") == affiliation_record.disambiguation_source):
                    affiliation_record.put_code = put_code
                    return True

                if affiliation_record.put_code:
                    return

                if put_code in taken_put_codes:
                    continue

                if ((r.get("start-date") is None and r.get("end-date") is None
                     and r.get("department-name") is None and r.get("role-title") is None)
                        or (r.get("start-date") == start_date
                            and r.get("department-name") == affiliation_record.department
                            and r.get("role-title") == affiliation_record.role)):
                    affiliation_record.put_code = put_code
                    taken_put_codes.add(put_code)
                    app.logger.debug(
                        f"put-code {put_code} was asigned to the affiliation record "
                        f"(ID: {affiliation_record.id}, Task ID: {affiliation_record.task_id})")
                    break

        for task_by_user in records:
            try:
                ar = task_by_user.affiliation_record
                at = ar.affiliation_type.lower()
                no_orcid_call = False

                if at in EMP_CODES:
                    no_orcid_call = match_put_code(employments, ar)
                    affiliation = Affiliation.EMP
                elif at in EDU_CODES:
                    no_orcid_call = match_put_code(educations, ar)
                    affiliation = Affiliation.EDU
                else:
                    logger.info(f"For {user} not able to determine affiliaton type with {org}")
                    ar.add_status_line(
                        f"Unsupported affiliation type '{at}' allowed values are: " + ', '.join(
                            at for at in AFFILIATION_TYPES))
                    ar.save()
                    continue

                if no_orcid_call:
                    ar.add_status_line(f"{str(affiliation)} record unchanged.")
                else:
                    put_code, orcid, created = api.create_or_update_affiliation(
                        affiliation=affiliation, **ar._data)
                    if created:
                        ar.add_status_line(f"{str(affiliation)} record was created.")
                    else:
                        ar.add_status_line(f"{str(affiliation)} record was updated.")
                    ar.orcid = orcid
                    ar.put_code = put_code

            except Exception as ex:
                logger.exception(f"For {user} encountered exception")
                ar.add_status_line(f"Exception occured processing the record: {ex}.")

            finally:
                ar.processed_at = datetime.utcnow()
                ar.save()
    else:
        for task_by_user in records:
            user = User.get(
                email=task_by_user.affiliation_record.email, organisation=task_by_user.org)
            user_org = UserOrg.get(user=user, org=task_by_user.org)
            token = generate_confirmation_token(email=user.email, org=org.name)
            with app.app_context():
                url = flask.url_for('orcid_login', invitation_token=token, _external=True)
                invitation_url = flask.url_for(
                    "short_url", short_id=Url.shorten(url).short_id, _external=True)
                send_email(
                    "email/researcher_reinvitation.html",
                    recipient=(user.organisation.name, user.email),
                    reply_to=(task_by_user.created_by.name, task_by_user.created_by.email),
                    invitation_url=invitation_url,
                    org_name=user.organisation.name,
                    org=org,
                    user=user)
            UserInvitation.create(
                invitee_id=user.id,
                inviter_id=task_by_user.created_by.id,
                org=org,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                orcid=user.orcid,
                organisation=org.name,
                city=org.city,
                state=org.state,
                country=org.country,
                start_date=task_by_user.affiliation_record.start_date,
                end_date=task_by_user.affiliation_record.end_date,
                affiliations=user_org.affiliations,
                disambiguated_id=org.disambiguated_id,
                disambiguation_source=org.disambiguation_source,
                token=token)

            status = "Exception occured while accessing user's profile. " \
                     "Hence, The invitation resent at " + datetime.utcnow().isoformat(timespec="seconds")
            (AffiliationRecord.update(status=AffiliationRecord.status + "\n" + status).where(
                AffiliationRecord.status.is_null(False),
                AffiliationRecord.email == user.email).execute())
            (AffiliationRecord.update(status=status).where(
                AffiliationRecord.status.is_null(),
                AffiliationRecord.email == user.email).execute())
            return


@rq.job(timeout=300)
def process_work_records(max_rows=20):
    """Process uploaded work records."""
    set_server_name()
    task_ids = set()
    work_ids = set()
    """This query is to retrieve Tasks associated with work records, which are not processed but are active"""

    tasks = (Task.select(
        Task, WorkRecord, WorkInvitees,
        User, UserInvitation.id.alias("invitation_id"), OrcidToken).where(
            WorkRecord.processed_at.is_null(), WorkInvitees.processed_at.is_null(),
            WorkRecord.is_active,
            (OrcidToken.id.is_null(False) |
             ((WorkInvitees.status.is_null()) |
              (WorkInvitees.status.contains("sent").__invert__())))).join(
                  WorkRecord, on=(Task.id == WorkRecord.task_id)).join(
                      WorkInvitees,
                      on=(WorkRecord.id == WorkInvitees.work_record_id)).join(
                          User, JOIN.LEFT_OUTER,
                          on=((User.email == WorkInvitees.email) | (User.orcid == WorkInvitees.orcid)))
             .join(Organisation, JOIN.LEFT_OUTER, on=(Organisation.id == Task.org_id)).join(
                 UserInvitation,
                 JOIN.LEFT_OUTER,
                 on=((UserInvitation.email == WorkInvitees.email)
                     & (UserInvitation.task_id == Task.id))).join(
                         OrcidToken,
                         JOIN.LEFT_OUTER,
                         on=((OrcidToken.user_id == User.id)
                             & (OrcidToken.org_id == Organisation.id)
                             & (OrcidToken.scope.contains("/activities/update")))).limit(max_rows))

    for (task_id, org_id, work_record_id, user), tasks_by_user in groupby(tasks, lambda t: (
            t.id,
            t.org_id,
            t.work_record.id,
            t.work_record.work_invitees.user,)):
        """If we have the token associated to the user then update the work record, otherwise send him an invite"""
        if (user.id is None or user.orcid is None or not OrcidToken.select().where(
            (OrcidToken.user_id == user.id) & (OrcidToken.org_id == org_id) &
            (OrcidToken.scope.contains("/activities/update"))).exists()):  # noqa: E127, E129

            for k, tasks in groupby(
                    tasks_by_user,
                    lambda t: (
                        t.created_by,
                        t.org,
                        t.work_record.work_invitees.email,
                        t.work_record.work_invitees.first_name,
                        t.work_record.work_invitees.last_name, )
            ):  # noqa: E501
                email = k[2]
                token_expiry_in_sec = 2600000
                status = "The invitation sent at " + datetime.utcnow().isoformat(timespec="seconds")
                try:
                    # For researcher invitation the expiry is 30 days, if it is reset then it is 2 weeks.
                    if WorkInvitees.select().where(WorkInvitees.email == email,
                                                   WorkInvitees.status ** "%reset%").count() != 0:
                        token_expiry_in_sec = 1300000
                    send_work_funding_peer_review_invitation(*k, task_id=task_id,
                                                             token_expiry_in_sec=token_expiry_in_sec,
                                                             invitation_template="email/work_invitation.html")

                    (WorkInvitees.update(status=WorkInvitees.status + "\n" + status).where(
                        WorkInvitees.status.is_null(False), WorkInvitees.email == email).execute())
                    (WorkInvitees.update(status=status).where(
                        WorkInvitees.status.is_null(), WorkInvitees.email == email).execute())
                except Exception as ex:
                    (WorkInvitees.update(processed_at=datetime.utcnow(), status=f"Failed to send an invitation: {ex}.")
                     .where(WorkInvitees.email == email, WorkInvitees.processed_at.is_null())).execute()
        else:
            create_or_update_work(user, org_id, tasks_by_user)
        task_ids.add(task_id)
        work_ids.add(work_record_id)

    for work_record in WorkRecord.select().where(WorkRecord.id << work_ids):
        # The Work record is processed for all invitees
        if not (WorkInvitees.select().where(
                WorkInvitees.work_record_id == work_record.id,
                WorkInvitees.processed_at.is_null()).exists()):
            work_record.processed_at = datetime.utcnow()
            if not work_record.status or "error" not in work_record.status:
                work_record.add_status_line("Work record is processed.")
            work_record.save()

    for task in Task.select().where(Task.id << task_ids):
        # The task is completed (Once all records are processed):
        if not (WorkRecord.select().where(WorkRecord.task_id == task.id, WorkRecord.processed_at.is_null()).exists()):
            task.completed_at = datetime.utcnow()
            task.save()
            error_count = WorkRecord.select().where(
                WorkRecord.task_id == task.id, WorkRecord.status**"%error%").count()
            row_count = task.record_count

            with app.app_context():
                protocol_scheme = 'http'
                if not EXTERNAL_SP:
                    protocol_scheme = 'https'
                export_url = flask.url_for(
                    "workrecord.export",
                    export_type="json",
                    _scheme=protocol_scheme,
                    task_id=task.id,
                    _external=True)
                send_email(
                    "email/work_task_completed.html",
                    subject="Work Process Update",
                    recipient=(task.created_by.name, task.created_by.email),
                    error_count=error_count,
                    row_count=row_count,
                    export_url=export_url,
                    task_name="Work",
                    filename=task.filename)


def process_peer_review_records(max_rows=20):
    """Process uploaded peer_review records."""
    set_server_name()
    task_ids = set()
    peer_review_ids = set()
    """This query is to retrieve Tasks associated with peer review records, which are not processed but are active"""
    tasks = (Task.select(
        Task, PeerReviewRecord, PeerReviewInvitee,
        User, UserInvitation.id.alias("invitation_id"), OrcidToken).where(
            PeerReviewRecord.processed_at.is_null(), PeerReviewInvitee.processed_at.is_null(),
            PeerReviewRecord.is_active,
            (OrcidToken.id.is_null(False) |
             ((PeerReviewInvitee.status.is_null()) |
              (PeerReviewInvitee.status.contains("sent").__invert__())))).join(
                  PeerReviewRecord, on=(Task.id == PeerReviewRecord.task_id)).join(
                      PeerReviewInvitee,
                      on=(PeerReviewRecord.id == PeerReviewInvitee.peer_review_record_id)).join(
                          User, JOIN.LEFT_OUTER,
                          on=((User.email == PeerReviewInvitee.email) | (User.orcid == PeerReviewInvitee.orcid)))
             .join(Organisation, JOIN.LEFT_OUTER, on=(Organisation.id == Task.org_id)).join(
                 UserInvitation,
                 JOIN.LEFT_OUTER,
                 on=((UserInvitation.email == PeerReviewInvitee.email)
                     & (UserInvitation.task_id == Task.id))).join(
                         OrcidToken,
                         JOIN.LEFT_OUTER,
                         on=((OrcidToken.user_id == User.id)
                             & (OrcidToken.org_id == Organisation.id)
                             & (OrcidToken.scope.contains("/activities/update")))).limit(max_rows))

    for (task_id, org_id, peer_review_record_id, user), tasks_by_user in groupby(tasks, lambda t: (
            t.id,
            t.org_id,
            t.peer_review_record.id,
            t.peer_review_record.peer_review_invitee.user,)):
        """If we have the token associated to the user then update the peer record, otherwise send him an invite"""
        if (user.id is None or user.orcid is None or not OrcidToken.select().where(
            (OrcidToken.user_id == user.id) & (OrcidToken.org_id == org_id) &
            (OrcidToken.scope.contains("/activities/update"))).exists()):  # noqa: E127, E129

            for k, tasks in groupby(
                    tasks_by_user,
                    lambda t: (
                        t.created_by,
                        t.org,
                        t.peer_review_record.peer_review_invitee.email,
                        t.peer_review_record.peer_review_invitee.first_name,
                        t.peer_review_record.peer_review_invitee.last_name, )
            ):  # noqa: E501
                email = k[2]
                token_expiry_in_sec = 2600000
                status = "The invitation sent at " + datetime.utcnow().isoformat(timespec="seconds")
                try:
                    if PeerReviewInvitee.select().where(PeerReviewInvitee.email == email,
                                                        PeerReviewInvitee.status ** "%reset%").count() != 0:
                        token_expiry_in_sec = 1300000
                    send_work_funding_peer_review_invitation(*k, task_id=task_id,
                                                             token_expiry_in_sec=token_expiry_in_sec,
                                                             invitation_template="email/peer_review_invitation.html")

                    (PeerReviewInvitee.update(status=PeerReviewInvitee.status + "\n" + status).where(
                        PeerReviewInvitee.status.is_null(False), PeerReviewInvitee.email == email).execute())
                    (PeerReviewInvitee.update(status=status).where(
                        PeerReviewInvitee.status.is_null(), PeerReviewInvitee.email == email).execute())
                except Exception as ex:
                    (PeerReviewInvitee.update(processed_at=datetime.utcnow(),
                                              status=f"Failed to send an invitation: {ex}.")
                     .where(PeerReviewInvitee.email == email, PeerReviewInvitee.processed_at.is_null())).execute()
        else:
            create_or_update_peer_review(user, org_id, tasks_by_user)
        task_ids.add(task_id)
        peer_review_ids.add(peer_review_record_id)

    for peer_review_record in PeerReviewRecord.select().where(PeerReviewRecord.id << peer_review_ids):
        # The Peer Review record is processed for all invitees
        if not (PeerReviewInvitee.select().where(
                PeerReviewInvitee.peer_review_record_id == peer_review_record.id,
                PeerReviewInvitee.processed_at.is_null()).exists()):
            peer_review_record.processed_at = datetime.utcnow()
            if not peer_review_record.status or "error" not in peer_review_record.status:
                peer_review_record.add_status_line("Peer Review record is processed.")
            peer_review_record.save()

    for task in Task.select().where(Task.id << task_ids):
        # The task is completed (Once all records are processed):
        if not (PeerReviewRecord.select().where(PeerReviewRecord.task_id == task.id,
                                                PeerReviewRecord.processed_at.is_null()).exists()):
            task.completed_at = datetime.utcnow()
            task.save()
            error_count = PeerReviewRecord.select().where(
                PeerReviewRecord.task_id == task.id, PeerReviewRecord.status ** "%error%").count()
            row_count = task.record_count

            with app.app_context():
                protocol_scheme = 'http'
                if not EXTERNAL_SP:
                    protocol_scheme = 'https'
                export_url = flask.url_for(
                    "peerreviewrecord.export",
                    export_type="json",
                    _scheme=protocol_scheme,
                    task_id=task.id,
                    _external=True)
                send_email(
                    "email/work_task_completed.html",
                    subject="Peer Review Process Update",
                    recipient=(task.created_by.name, task.created_by.email),
                    error_count=error_count,
                    row_count=row_count,
                    export_url=export_url,
                    task_name="Peer Review",
                    filename=task.filename)


def process_funding_records(max_rows=20):
    """Process uploaded affiliation records."""
    set_server_name()
    task_ids = set()
    funding_ids = set()
    """This query is to retrieve Tasks associated with funding records, which are not processed but are active"""
    tasks = (Task.select(
        Task, FundingRecord, FundingInvitees,
        User, UserInvitation.id.alias("invitation_id"), OrcidToken).where(
            FundingRecord.processed_at.is_null(), FundingInvitees.processed_at.is_null(),
            FundingRecord.is_active,
            (OrcidToken.id.is_null(False) |
             ((FundingInvitees.status.is_null()) |
              (FundingInvitees.status.contains("sent").__invert__())))).join(
                  FundingRecord, on=(Task.id == FundingRecord.task_id)).join(
                      FundingInvitees,
                      on=(FundingRecord.id == FundingInvitees.funding_record_id)).join(
                          User,
                          JOIN.LEFT_OUTER,
                          on=((User.email == FundingInvitees.email) |
                              (User.orcid == FundingInvitees.orcid)))
             .join(Organisation, JOIN.LEFT_OUTER, on=(Organisation.id == Task.org_id)).join(
                 UserInvitation,
                 JOIN.LEFT_OUTER,
                 on=((UserInvitation.email == FundingInvitees.email)
                     & (UserInvitation.task_id == Task.id))).join(
                         OrcidToken,
                         JOIN.LEFT_OUTER,
                         on=((OrcidToken.user_id == User.id)
                             & (OrcidToken.org_id == Organisation.id)
                             & (OrcidToken.scope.contains("/activities/update")))).limit(max_rows))

    for (task_id, org_id, funding_record_id, user), tasks_by_user in groupby(tasks, lambda t: (
            t.id,
            t.org_id,
            t.funding_record.id,
            t.funding_record.funding_invitees.user,)):
        """If we have the token associated to the user then update the funding record, otherwise send him an invite"""
        if (user.id is None or user.orcid is None or not OrcidToken.select().where(
            (OrcidToken.user_id == user.id) & (OrcidToken.org_id == org_id) &
            (OrcidToken.scope.contains("/activities/update"))).exists()):  # noqa: E127, E129

            for k, tasks in groupby(
                    tasks_by_user,
                    lambda t: (
                        t.created_by,
                        t.org,
                        t.funding_record.funding_invitees.email,
                        t.funding_record.funding_invitees.first_name,
                        t.funding_record.funding_invitees.last_name, )
            ):  # noqa: E501
                email = k[2]
                token_expiry_in_sec = 2600000
                status = "The invitation sent at " + datetime.utcnow().isoformat(timespec="seconds")
                try:
                    if FundingInvitees.select().where(FundingInvitees.email == email,
                                                      FundingInvitees.status ** "%reset%").count() != 0:
                        token_expiry_in_sec = 1300000
                    send_work_funding_peer_review_invitation(*k, task_id=task_id,
                                                             token_expiry_in_sec=token_expiry_in_sec,
                                                             invitation_template="email/funding_invitation.html")

                    (FundingInvitees.update(status=FundingInvitees.status + "\n" + status).where(
                        FundingInvitees.status.is_null(False), FundingInvitees.email == email).execute())
                    (FundingInvitees.update(status=status).where(
                        FundingInvitees.status.is_null(), FundingInvitees.email == email).execute())
                except Exception as ex:
                    (FundingInvitees.update(processed_at=datetime.utcnow(),
                                            status=f"Failed to send an invitation: {ex}.")
                     .where(FundingInvitees.email == email, FundingInvitees.processed_at.is_null())).execute()
        else:
            create_or_update_funding(user, org_id, tasks_by_user)
        task_ids.add(task_id)
        funding_ids.add(funding_record_id)

    for funding_record in FundingRecord.select().where(FundingRecord.id << funding_ids):
        # The funding record is processed for all invitees
        if not (FundingInvitees.select().where(
                FundingInvitees.funding_record_id == funding_record.id,
                FundingInvitees.processed_at.is_null()).exists()):
            funding_record.processed_at = datetime.utcnow()
            if not funding_record.status or "error" not in funding_record.status:
                funding_record.add_status_line("Funding record is processed.")
            funding_record.save()

    for task in Task.select().where(Task.id << task_ids):
        # The task is completed (Once all records are processed):
        if not (FundingRecord.select().where(FundingRecord.task_id == task.id,
                                             FundingRecord.processed_at.is_null()).exists()):
            task.completed_at = datetime.utcnow()
            task.save()
            error_count = FundingRecord.select().where(
                FundingRecord.task_id == task.id, FundingRecord.status**"%error%").count()
            row_count = task.record_count

            with app.app_context():
                protocol_scheme = 'http'
                if not EXTERNAL_SP:
                    protocol_scheme = 'https'
                export_url = flask.url_for(
                    "fundingrecord.export",
                    export_type="json",
                    _scheme=protocol_scheme,
                    task_id=task.id,
                    _external=True)
                send_email(
                    "email/funding_task_completed.html",
                    subject="Funding Process Update",
                    recipient=(task.created_by.name, task.created_by.email),
                    error_count=error_count,
                    row_count=row_count,
                    export_url=export_url,
                    filename=task.filename)


def process_affiliation_records(max_rows=20):
    """Process uploaded affiliation records."""
    set_server_name()
    # TODO: optimize removing redundant fields
    # TODO: perhaps it should be broken into 2 queries
    task_ids = set()
    tasks = (Task.select(
        Task, AffiliationRecord, User, UserInvitation.id.alias("invitation_id"), OrcidToken).where(
            AffiliationRecord.processed_at.is_null(), AffiliationRecord.is_active,
            ((User.id.is_null(False) & User.orcid.is_null(False) & OrcidToken.id.is_null(False)) |
             ((User.id.is_null() | User.orcid.is_null() | OrcidToken.id.is_null()) &
              UserInvitation.id.is_null() &
              (AffiliationRecord.status.is_null()
               | AffiliationRecord.status.contains("sent").__invert__())))).join(
                   AffiliationRecord, on=(Task.id == AffiliationRecord.task_id)).join(
                       User,
                       JOIN.LEFT_OUTER,
                       on=((User.email == AffiliationRecord.email) |
                           (User.orcid == AffiliationRecord.orcid))).join(
                               Organisation, JOIN.LEFT_OUTER, on=(Organisation.id == Task.org_id))
             .join(
                 UserInvitation,
                 JOIN.LEFT_OUTER,
                 on=((UserInvitation.email == AffiliationRecord.email) &
                     (UserInvitation.task_id == Task.id))).join(
                         OrcidToken,
                         JOIN.LEFT_OUTER,
                         on=((OrcidToken.user_id == User.id) &
                             (OrcidToken.org_id == Organisation.id) &
                             (OrcidToken.scope.contains("/activities/update")))).limit(max_rows))
    for (task_id, org_id, user), tasks_by_user in groupby(tasks, lambda t: (
            t.id,
            t.org_id,
            t.affiliation_record.user, )):
        if (user.id is None or user.orcid is None or not OrcidToken.select().where(
            (OrcidToken.user_id == user.id) & (OrcidToken.org_id == org_id) &
            (OrcidToken.scope.contains("/activities/update"))).exists()):  # noqa: E127, E129

            # maps invitation attributes to affiliation type set:
            # - the user who uploaded the task;
            # - the user organisation;
            # - the invitee email;
            # - the invitee first_name;
            # - the invitee last_name
            invitation_dict = {
                k: set(t.affiliation_record.affiliation_type.lower() for t in tasks)
                for k, tasks in groupby(
                    tasks_by_user,
                    lambda t: (t.created_by, t.org, t.affiliation_record.email, t.affiliation_record.first_name, t.affiliation_record.last_name)  # noqa: E501
                )  # noqa: E501
            }
            for invitation, affiliations in invitation_dict.items():
                email = invitation[2]
                token_expiry_in_sec = 2600000
                try:
                    # For researcher invitation the expiry is 30 days, if it is reset then it 2 weeks.
                    if AffiliationRecord.select().where(AffiliationRecord.task_id == task_id,
                                                        AffiliationRecord.email == email,
                                                        AffiliationRecord.status ** "%reset%").count() != 0:
                        token_expiry_in_sec = 1300000
                    send_user_invitation(*invitation, affiliations, task_id=task_id,
                                         token_expiry_in_sec=token_expiry_in_sec)
                except Exception as ex:
                    (AffiliationRecord.update(
                        processed_at=datetime.utcnow(), status=f"Failed to send an invitation: {ex}.")
                     .where(AffiliationRecord.task_id == task_id, AffiliationRecord.email == email,
                            AffiliationRecord.processed_at.is_null())).execute()
        else:  # user exits and we have tokens
            create_or_update_affiliations(user, org_id, tasks_by_user)
        task_ids.add(task_id)
    for task in Task.select().where(Task.id << task_ids):
        # The task is completed (all recores are processed):
        if not (AffiliationRecord.select().where(
                AffiliationRecord.task_id == task.id,
                AffiliationRecord.processed_at.is_null()).exists()):
            task.completed_at = datetime.utcnow()
            task.save()
            error_count = AffiliationRecord.select().where(
                AffiliationRecord.task_id == task.id, AffiliationRecord.status**"%error%").count()
            row_count = task.record_count
            orcid_rec_count = task.affiliation_records.select(
                AffiliationRecord.orcid).distinct().count()

            with app.app_context():
                protocol_scheme = 'http'
                if not EXTERNAL_SP:
                    protocol_scheme = 'https'
                export_url = flask.url_for(
                    "affiliationrecord.export",
                    export_type="csv",
                    _scheme=protocol_scheme,
                    task_id=task.id,
                    _external=True)
                try:
                    send_email(
                        "email/task_completed.html",
                        subject="Affiliation Process Update",
                        recipient=(task.created_by.name, task.created_by.email),
                        error_count=error_count,
                        row_count=row_count,
                        orcid_rec_count=orcid_rec_count,
                        export_url=export_url,
                        filename=task.filename)
                except Exception:
                    logger.exception(
                        "Failed to send batch process comletion notification message.")


@rq.job(timeout=300)
def process_tasks(max_rows=20):
    """Handle batch task expiration.

    Send a information messages about upcoming removal of the processed/uploaded tasks
    based on date whichever is greater either created_at + month or updated_at + 2 weeks
    and removal of expired tasks based on the expiry date.

    Args:
        max_rows (int): The maximum number of rows that will get processed in one go.

    Returns:
        int. The number of processed task records.

    """
    Task.delete().where((Task.expires_at < datetime.utcnow())).execute()

    tasks = Task.select().where(Task.expires_at.is_null())
    if max_rows and max_rows > 0:
        tasks = tasks.limit(max_rows)
    for task in tasks:

        max_created_at_expiry = (task.created_at + timedelta(weeks=4))
        max_updated_at_expiry = (task.updated_at + timedelta(weeks=2))

        max_expiry_date = max_created_at_expiry

        if max_created_at_expiry < max_updated_at_expiry:
            max_expiry_date = max_updated_at_expiry

        task.expires_at = max_expiry_date
        task.save()

    tasks = Task.select().where(
            Task.expires_at.is_null(False),
            Task.expiry_email_sent_at.is_null(),
            Task.expires_at < (datetime.now() + timedelta(weeks=1)))
    if max_rows and max_rows > 0:
        tasks = tasks.limit(max_rows)
    for task in tasks:

        export_model = task.record_model._meta.name + ".export"
        error_count = task.error_count

        set_server_name()
        with app.app_context():
            protocol_scheme = 'http'
            if not EXTERNAL_SP:
                protocol_scheme = 'https'
            export_url = flask.url_for(
                export_model,
                export_type="csv",
                _scheme=protocol_scheme,
                task_id=task.id,
                _external=True)
            send_email(
                "email/task_expiration.html",
                task=task,
                subject="Batch process task is about to expire",
                recipient=(task.created_by.name, task.created_by.email),
                error_count=error_count,
                export_url=export_url)
        task.expiry_email_sent_at = datetime.utcnow()
        task.save()


def get_client_credentials_token(org, scope="/webhook"):
    """Request a cient credetials grant type access token and store it.

    The any previously requesed with the give scope tokens will be deleted.
    """
    resp = requests.post(
        app.config["TOKEN_URL"],
        headers={"Accept": "application/json"},
        data=dict(
            client_id=org.orcid_client_id,
            client_secret=org.orcid_secret,
            scope=scope,
            grant_type="client_credentials"))
    OrcidToken.delete().where(OrcidToken.org == org, OrcidToken.scope == "/webhook").execute()
    data = resp.json()
    token = OrcidToken.create(
        org=org,
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        scope=data.get("scope") or scope,
        expires_in=data["expires_in"])
    return token


@rq.job(timeout=300)
def register_orcid_webhook(user, callback_url=None, delete=False):
    """Register or delete an ORCID webhook for the given user profile update events.

    If URL is given, it will be used for as call-back URL.
    """
    set_server_name()
    local_handler = (callback_url is None)

    if local_handler and delete and user.organisations.where(Organisation.webhook_enabled).count() > 0:
        return

    try:
        token = OrcidToken.get(org=user.organisation, scope="/webhook")
    except OrcidToken.DoesNotExist:
        token = get_client_credentials_token(org=user.organisation, scope="/webhook")
    if local_handler:
        with app.app_context():
            callback_url = quote(url_for("update_webhook", user_id=user.id), safe='')
    elif '/' in callback_url or ':' in callback_url:
        callback_url = quote(callback_url, safe='')
    url = f"{app.config['ORCID_API_HOST_URL']}{user.orcid}/webhook/{callback_url}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token.access_token}",
        "Content-Length": "0"
    }
    resp = requests.delete(url, headers=headers) if delete else requests.put(url, headers=headers)
    if local_handler and resp.status_code // 100 == 2:
        if delete:
            user.webhook_enabled = False
        else:
            user.webhook_enabled = True
        user.save()
    return resp


@rq.job(timeout=300)
def invoke_webhook_handler(webhook_url, orcid, updated_at, attempts=3):
    """Propagate 'updated' event to the organisation event handler URL."""
    url = app.config["ORCID_BASE_URL"] + orcid
    resp = requests.post(
        webhook_url + '/' + orcid,
        json={
            "orcid": orcid,
            "updated-at": updated_at.isoformat(timespec="minutes"),
            "url": url
        })
    if resp.status_code // 100 != 2:
        if attempts > 0:
            invoke_webhook_handler.schedule(
                timedelta(minutes=5),
                webhook_url=webhook_url,
                orcid=orcid,
                updated_at=updated_at,
                attempts=attempts - 1)
    return resp


@rq.job(timeout=300)
def enable_org_webhook(org):
    """Enable Organisation Webhook."""
    org.webhook_enabled = True
    org.save()
    for u in org.users:
        if not u.webhook_enabled:
            register_orcid_webhook.queue(u)


@rq.job(timeout=300)
def disable_org_webhook(org):
    """Disable Organisation Webhook."""
    org.webhook_enabled = False
    org.save()
    for u in org.users.where(User.webhook_enabled):
        register_orcid_webhook.queue(u, delete=True)


def process_records(n):
    """Process first n records and run other batch tasks."""
    process_affiliation_records(n)
    process_funding_records(n)
    process_work_records(n)
    process_peer_review_records(n)
    # process_tasks(n)
