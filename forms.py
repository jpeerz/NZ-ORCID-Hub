# -*- coding: utf-8 -*-
"""Application forms."""

from datetime import date

from flask_wtf import FlaskForm
from pycountry import countries
from wtforms import (Field, SelectField, SelectMultipleField, StringField, validators)
from wtforms.widgets import HTMLString, html_params

from models import PartialDate as PD

# Order the countly list by the name and add a default (Null) value
country_choices = [(c.alpha_2, c.name) for c in countries]
country_choices.sort(key=lambda e: e[1])
country_choices.insert(0, ("", "Country"))


class PartialDate:
    """Widget for a partical date with 3 selectors (year, month, day)."""

    __current_year = date.today().year

    def __call__(self, field, **kwargs):
        """Render widget."""
        kwargs.setdefault('id', field.id)
        html = [
            "<!-- data: %r -->" % (field.data, ),
            '<div %s>' % html_params(name=field.name, **kwargs)
        ]
        html.extend(self.render_select("year", field))
        html.extend(self.render_select("month", field))
        html.extend(self.render_select("day", field))
        html.append("</div>")
        return HTMLString(''.join(html))

    @classmethod
    def render_select(cls, part, field):
        """Render select for a specific part of date."""
        yield "<select %s>" % html_params(name=field.name + ":" + part)
        try:
            current_value = int(getattr(field.data, part))
        except:
            current_value = None
        # TODO: localization
        yield "<option %s>%s</option>" % (html_params(value="", selected=(current_value is None)),
                                          part.capitalize())
        option_format = "<option %s>%04d</option>" if part == "year" else "<option %s>%02d</option>"
        for v in range(cls.__current_year, 1912, -1) if part == "year" else range(
                1, 13 if part == "month" else 32):
            yield option_format % (html_params(value=v, selected=(v == current_value)), v)
        yield "</select>"


class PartialDateField(Field):
    """Partial date field."""

    widget = PartialDate()

    def process(self, formdata, data=None):
        """Process incoming data, calling process_data."""

        self.process_errors = []
        if data is None:
            data = self.default or PD()

        # self.object_data = data
        self.data = data

        if formdata is not None:
            new_data = {}
            for f in ("year", "month", "day", ):
                try:
                    if (self.name + ":" + f) in formdata:
                        raw_val = formdata.get(self.name + ":" + f)
                        value = int(raw_val) if raw_val else None
                    else:
                        value = getattr(self.data, f)
                    new_data[f] = value
                except ValueError as e:
                    new_data[f] = None
                    self.process_errors.append(e.args[0])
            self.data = PD(**new_data)
        try:
            for filter in self.filters:
                self.data = filter(self.data)
        except ValueError as e:
            self.process_errors.append(e.args[0])


class BitmapMultipleValueField(SelectMultipleField):
    """
    No different from a normal multi select field, except this one can take (and
    validate) multiple choices and value (by defualt) can be a bitmap of
    selected choices (the choice value should be an integer).
    """
    bitmap_value = True

    def process_data(self, value):
        try:
            if self.bitmap_value:
                self.data = [self.coerce(v) for (v, _) in self.choices if v & value]
            else:
                self.data = [self.coerce(v) for v in value]
        except (ValueError, TypeError):
            self.data = None

    def process_formdata(self, valuelist):
        try:
            if self.bitmap_value:
                self.data = sum(int(self.coerce(x)) for x in valuelist)
            else:
                self.data = [self.coerce(x) for x in valuelist]
        except ValueError:
            raise ValueError(
                self.gettext('Invalid choice(s): one or more data inputs could not be coerced'))

    def pre_validate(self, form):
        if self.data and not self.bitmap_value:
            values = list(c[0] for c in self.choices)
            for d in self.data:
                if d not in values:
                    raise ValueError(
                        self.gettext("'%(value)s' is not a valid choice for this field") % dict(
                            value=d))


class EmploymentForm(FlaskForm):
    """User/researcher employment detail form."""

    name = StringField("Institution/employer", [validators.required()])
    city = StringField("City", [validators.required()])
    state = StringField("State/region", filters=[lambda x: x or None])
    country = SelectField("Country", [validators.required()], choices=country_choices)
    department = StringField("Department", filters=[lambda x: x or None])
    role = StringField("Role/title", filters=[lambda x: x or None])
    start_date = PartialDateField("Start date")
    end_date = PartialDateField("End date (leave blank if current)")


class EducationForm(FlaskForm):
    """User/researcher education detail form."""

    name = StringField("Institution", [validators.required()])
    city = StringField("City", [validators.required()])
    state = StringField("State/region")
    country = SelectField("Country", [validators.required()], choices=country_choices)
    role = StringField("Role/title", filters=[lambda x: x or None])
    department = StringField("Department", filters=[lambda x: x or None])
    start_date = PartialDateField("Start date")
    end_date = PartialDateField("End date (leave blank if current)")