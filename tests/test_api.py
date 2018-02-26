# -*- coding: utf-8 -*-
"""Tests for core functions."""

import copy
import json

import pytest
from flask import url_for
from flask_login import login_user

from orcid_hub.apis import yamlfy
from orcid_hub.models import Client, OrcidToken, Organisation, Role, Task, TaskType, Token, User, UserOrg


@pytest.fixture
def app_req_ctx(request_ctx):
    """Create the fixture for the reques with a test organisation and a test tech.contatct."""
    org = Organisation.create(
        name="THE ORGANISATION",
        tuakiri_name="THE ORGANISATION",
        confirmed=True,
        city="CITY",
        country="COUNTRY")

    admin = User.create(
        email="app123@test0.edu",
        name="TEST USER WITH AN APP",
        roles=Role.TECHNICAL,
        orcid="1001-0001-0001-0001",
        confirmed=True,
        organisation=org)

    UserOrg.create(user=admin, org=org, is_admin=True)
    org.tech_contact = admin
    org.save()

    client = Client.create(
        name="TEST_CLIENT",
        user=admin,
        org=org,
        client_id="CLIENT_ID",
        client_secret="CLIENT_SECRET",
        is_confidential="public",
        grant_type="client_credentials",
        response_type="XYZ")

    Token.create(client=client, user=admin, access_token="TEST", token_type="Bearer")

    user = User.create(
        email="researcher@test0.edu",
        eppn="eppn@test0.edu",
        name="TEST REASEARCHER",
        orcid="0000-0000-0000-00X3",
        confirmed=True,
        organisation=org)

    OrcidToken.create(user=user, org=org, access_token="ORCID-TEST-ACCESS-TOKEN")

    User.create(
        email="researcher2@test0.edu",
        eppn="eppn2@test0.edu",
        name="TEST REASEARCHER W/O ORCID ACCESS TOKEN",
        orcid="0000-0000-0000-11X2",
        confirmed=True,
        organisation=org)

    org2 = Organisation.create(
        name="THE ORGANISATION #2",
        tuakiri_name="THE ORGANISATION #2",
        confirmed=True,
        city="CITY")
    User.create(
        email="researcher@org2.edu",
        eppn="eppn123@org2.edu",
        name="TEST REASEARCHER #2",
        orcid="9999-9999-9999-9999",
        confirmed=True,
        organisation=org2)

    return request_ctx


def test_get_oauth_access_token(app_req_ctx):
    """Test the acquisition of OAuth access token."""
    with app_req_ctx(
            "/oauth/token",
            method="POST",
            data=dict(
                grant_type="client_credentials",
                client_id="CLIENT_ID",
                client_secret="CLIENT_SECRET")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        data = json.loads(rv.data)
        client = Client.get(client_id="CLIENT_ID")
        token = Token.get(client=client)
        assert data["access_token"] == token.access_token
        assert data["expires_in"] == ctx.app.config["OAUTH2_PROVIDER_TOKEN_EXPIRES_IN"]
        assert data["token_type"] == token.token_type
        # prevously created access token should be removed
        assert not Token.select().where(Token.access_token == "TEST").exists()

    with app_req_ctx(
            "/oauth/token",
            method="POST",
            data=dict(
                grant_type="client_credentials",
                client_id="NOT-EXISTING-CLIENT_ID",
                client_secret="CLIENT_SECRET")) as ctx:
        # login_user(user, remember=True)
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 401
        data = json.loads(rv.data)
        assert data["error"] == "invalid_client"

    with app_req_ctx(
            "/oauth/token",
            method="POST",
            data=dict(
                grant_type="client_credentials",
                client_id="CLIENT_ID",
                client_secret="INCORRECT")) as ctx:
        # login_user(user, remember=True)
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 401
        data = json.loads(rv.data)
        assert data["error"] == "invalid_client"

    with app_req_ctx(
            "/oauth/token",
            method="POST",
            data=dict(
                grant_type="INCORRECT",
                client_id="NOT-EXISTING-CLIENT_ID",
                client_secret="CLIENT_SECRET")) as ctx:
        # login_user(user, remember=True)
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert data["error"] == "unsupported_grant_type"


# def test_revoke_access_token(app_req_ctx):
#     """Test the acquisition of OAuth access token."""
#     with app_req_ctx(
#             "/oauth/token",
#             method="POST",
#             data=dict(
#                 grant_type="client_credentials",
#                 client_id="CLIENT_ID",
#                 client_secret="CLIENT_SECRET")) as ctx:
#         rv = ctx.app.full_dispatch_request()
#         assert rv.status_code == 200
#         data = json.loads(rv.data)
#         client = Client.get(client_id="CLIENT_ID")
#         token = Token.get(client=client)
#         assert data["access_token"] == token.access_token

#     with app_req_ctx(
#             "/oauth/token",
#             method="POST",
#             data=dict(
#                 grant_type="client_credentials",
#                 client_id="CLIENT_ID",
#                 client_secret="CLIENT_SECRET")) as ctx:
#         rv = ctx.app.full_dispatch_request()
#         assert rv.status_code == 200
#         data = json.loads(rv.data)


def test_me(app_req_ctx):
    """Test the echo endpoint."""
    user = User.get(email="app123@test0.edu")
    token = Token.get(user=user)
    with app_req_ctx("/api/me", headers=dict(authorization=f"Bearer {token.access_token}")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["email"] == user.email
        assert data["name"] == user.name

    # Test invalid token:
    with app_req_ctx("/api/me", headers=dict(authorization="Bearer INVALID")) as ctx:
        user = User.get(email="app123@test0.edu")
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 401

    # Test expired token:
    from datetime import datetime
    token.expires = datetime(1971, 1, 1)
    token.save()
    with app_req_ctx("/api/me", headers=dict(authorization=f"Bearer {token.access_token}")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 401


@pytest.mark.parametrize("resource", [
    "users",
    "tokens",
])
@pytest.mark.parametrize("version", [
    "v0.1",
])
def test_user_and_token_api(app_req_ctx, resource, version):
    """Test the echo endpoint."""
    user = User.get(email="researcher@test0.edu")
    org2_user = User.get(email="researcher@org2.edu")
    with app_req_ctx(
            f"/api/{version}/{resource}/ABC123", headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert "error" in data
        assert "incorrect identifier" in data["error"].lower()
    with app_req_ctx(
            f"/api/{version}/{resource}/0000-0000-0000-0000",
            headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 400
        data = json.loads(rv.data)
        assert "error" in data
        assert "incorrect identifier" in data["error"].lower()
    with app_req_ctx(
            f"/api/{version}/{resource}/abc123@some.org",
            headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 404
        data = json.loads(rv.data)
        assert "error" in data
        assert "not found" in data["error"].lower()
    with app_req_ctx(
            f"/api/{version}/{resource}/0000-0000-0000-0001",
            headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 404
        data = json.loads(rv.data)
        assert "error" in data
        assert "not found" in data["error"].lower()
    for identifier in [
            user.email,
            user.orcid,
    ]:
        with app_req_ctx(
                f"/api/{version}/{resource}/{identifier}",
                headers=dict(authorization="Bearer TEST")) as ctx:
            rv = ctx.app.full_dispatch_request()
            data = json.loads(rv.data)
            assert rv.status_code == 200
            data = json.loads(rv.data)
            assert data["found"]
            if resource == "users":
                result = data["result"]
                assert result["email"] == user.email
                assert result["eppn"] == user.eppn
                assert result["orcid"] == user.orcid
            else:
                token = OrcidToken.get(user_id=user.id)
                assert data["token"]["access_token"] == token.access_token

    if resource == "tokens":
        user2 = User.get(email="researcher2@test0.edu")
        for identifier in [
                user2.email,
                user2.orcid,
        ]:
            with app_req_ctx(
                    f"/api/{version}/tokens/{identifier}",
                    headers=dict(authorization="Bearer TEST")) as ctx:
                rv = ctx.app.full_dispatch_request()
                assert rv.status_code == 404
                data = json.loads(rv.data)
                assert "error" in data

    with app_req_ctx(
            f"/api/{version}/{resource}/{org2_user.email}",
            headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 403
        data = json.loads(rv.data)
        assert "error" in data
        assert "Access Denied" in data["error"]


@pytest.mark.parametrize("url", [
    "/spec",
    "/spec.json",
    "/spec.yml",
])
def test_spec(client, url):
    """Test API specs."""
    rv = client.get(url)
    assert rv.status_code == 200


def test_yaml_spec(client):
    """Test API specs (the default entry point with yaml content type)."""
    rv = client.get("/spec", headers={"Accept": "text/yaml"})
    assert rv.status_code == 200


def test_yamlfy(app):
    """Test yamlfy function."""
    from flask import Response
    assert isinstance(yamlfy(1), Response)
    assert isinstance(yamlfy(1, 2, 3), Response)
    assert isinstance(yamlfy(key_arg=42), Response)
    with pytest.raises(TypeError):
        yamlfy(1, 2, 3, key_arg=42)


def test_api_docs(app_req_ctx):
    """Test API docs."""
    tech_contact = User.get(email="app123@test0.edu")
    with app_req_ctx("/api-docs/?url=http://SPECIFICATION") as ctx:
        login_user(tech_contact)
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        assert b"http://SPECIFICATION" in rv.data
    with app_req_ctx("/api-docs") as ctx:
        login_user(tech_contact)
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        assert url_for("spec", _external=True).encode("utf-8") in rv.data
    super_user = User.create(email="super_user@test0.edu", roles=Role.SUPERUSER, confirmed=True)
    with app_req_ctx("/db-api-docs/?url=http://SPECIFICATION") as ctx:
        login_user(super_user)
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        assert b"http://SPECIFICATION" in rv.data
    with app_req_ctx("/db-api-docs") as ctx:
        login_user(super_user)
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        assert url_for("Swagger.model_resources", _external=True).encode("utf-8") in rv.data


def test_db_api(app_req_ctx):
    """Test DB API."""
    with app_req_ctx(
            "/data/api/v0.1/organisations/", headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert "objects" in data
        assert len(data["objects"]) == 4

    with app_req_ctx("/data/api/v0.1/tasks/", headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert "objects" in data
        assert len(data["objects"]) == 0

    org = Organisation.get(id=1)
    with app_req_ctx(
            f"/data/api/v0.1/organisations/{org.id}",
            headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["name"] == org.name
        assert data["tuakiri_name"] == org.tuakiri_name

    org = Organisation.get(id=2)
    with app_req_ctx(
            f"/data/api/v0.1/organisations/{org.id}",
            headers=dict(authorization="Bearer TEST")) as ctx:
        rv = ctx.app.full_dispatch_request()
        assert rv.status_code == 200
        data = json.loads(rv.data)
        assert data["name"] == org.name
        assert data["tuakiri_name"] == org.tuakiri_name


def test_affiliation_api(client):
    """Test affiliation API in various formats."""
    resp = client.post(
        "/oauth/token",
        content_type="application/x-www-form-urlencoded",
        data=b"grant_type=client_credentials&client_id=TEST0-ID&client_secret=TEST0-SECRET")
    data = json.loads(resp.data)
    access_token = data["access_token"]
    resp = client.post(
        "/api/v0.1/affiliations/?filename=TEST42.csv",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="text/csv",
        data=b"First Name,Last Name,email,Organisation,Affiliation Type,Role,Department,Start Date,"
        b"End Date,City,State,Country,Disambiguated Id,Disambiguated Source\n"
        b"Researcher,Par,researcher.020@mailinator.com,Royal Org1,Staff,Programme Guide - "
        b"ORCID,Research Funding,2016-09,,Wellington,SATE,NZ,,\n"
        b"Roshan,Pawar,researcher.010@mailinator.com,Royal Org1,Staff,AAA,Research "
        b"Funding,2016-09,,Wellington,SATE,NZ,,\n"
        b"Roshan,Pawar,researcher.010@mailinator.com,Royal Org1,Student,BBB,Research "
        b"Funding,2016-09,,Wellington,SATE,New Zealand,,")
    data = json.loads(resp.data)
    assert data["filename"] == "TEST42.csv"
    assert data["task-type"] == "AFFILIATION"
    assert len(data["records"]) == 3
    task_id = data["id"]

    resp = client.get("/api/v0.1/tasks", headers=dict(authorization=f"Bearer {access_token}"))
    tasks = json.loads(resp.data)
    assert tasks[0]["id"] == task_id

    task_copy = copy.deepcopy(data)
    del(task_copy["id"])
    task_copy["filename"] = "TASK-COPY.csv"
    resp = client.post(
        "/api/v0.1/affiliations/",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(task_copy))
    assert Task.select().count() == 2

    for r in data["records"]:
        del(r["id"])
        r["city"] = "TEST000"
    resp = client.post(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(data))
    data = json.loads(resp.data)
    assert len(data["records"]) == 3
    # should get a new set of records

    del(data["records"][2])
    resp = client.post(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(data))
    new_data = json.loads(resp.data)
    assert len(new_data["records"]) == 2

    incorrect_data = copy.deepcopy(data)
    incorrect_data["records"].insert(0, {
        "first-name": "TEST000 FN",
        "last-name": "TEST000 LN",
    })
    resp = client.post(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(incorrect_data))
    data = json.loads(resp.data)
    assert resp.status_code == 422
    assert data["error"] == "Validation error."

    resp = client.get(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"))
    data = json.loads(resp.data)
    incorrect_data = copy.deepcopy(data)
    incorrect_data["records"].insert(0, {
        "email": "test1234@test.edu",
        "first-name": "TEST000 FN",
        "last-name": "TEST000 LN",
    })
    resp = client.post(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(incorrect_data))
    data = json.loads(resp.data)
    assert resp.status_code == 422
    assert data["error"] == "Validation error."

    resp = client.get(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"))
    data = json.loads(resp.data)
    new_data = copy.deepcopy(data)
    new_data["records"].insert(0, {
        "email": "test1234@test.edu",
        "first-name": "TEST000 FN",
        "last-name": "TEST000 LN",
        "affiliation-type": "staff",
        "city": "TEST000"
    })
    resp = client.post(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(new_data))
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert len(data["records"]) == 3

    resp = client.put(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(data))
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert len(data["records"]) == 3

    resp = client.get(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"))
    data = json.loads(resp.data)
    new_data = copy.deepcopy(data)
    for i, r in enumerate(new_data["records"]):
        new_data["records"][i] = {"id": r["id"], "is-active": True}
    resp = client.patch(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(new_data))
    data = json.loads(resp.data)
    assert resp.status_code == 200
    assert len(data["records"]) == 3
    assert all(r["is-active"] for r in data["records"])
    assert all(r["city"] == "TEST000" for r in data["records"])

    resp = client.head(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"))
    assert "Last-Modified" in resp.headers

    resp = client.head(
        "/api/v0.1/affiliations/999999999",
        headers=dict(authorization=f"Bearer {access_token}"))
    assert resp.status_code == 404

    resp = client.get(
        "/api/v0.1/affiliations/999999999",
        headers=dict(authorization=f"Bearer {access_token}"))
    assert resp.status_code == 404

    resp = client.patch(
        "/api/v0.1/affiliations/999999999",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(new_data))
    assert resp.status_code == 404

    resp = client.delete(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"))
    assert Task.select().count() == 1

    other_user = User.get(email="admin@test1.edu")
    other_task = Task.create(
        created_by=other_user,
        org=other_user.organisation,
        filename="OTHER.csv",
        task_type=TaskType.AFFILIATION)

    resp = client.head(
        f"/api/v0.1/affiliations/{other_task.id}",
        headers=dict(authorization=f"Bearer {access_token}"))
    assert resp.status_code == 403

    resp = client.get(
        f"/api/v0.1/affiliations/{other_task.id}",
        headers=dict(authorization=f"Bearer {access_token}"))
    assert resp.status_code == 403

    resp = client.patch(
        f"/api/v0.1/affiliations/{other_task.id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=json.dumps(new_data))
    assert resp.status_code == 403

    resp = client.delete(
        f"/api/v0.1/affiliations/{other_task.id}",
        headers=dict(authorization=f"Bearer {access_token}"))
    assert resp.status_code == 403

    resp = client.patch(
        f"/api/v0.1/affiliations/{task_id}",
        headers=dict(authorization=f"Bearer {access_token}"),
        content_type="application/json",
        data=b'')
    assert resp.status_code == 400