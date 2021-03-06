# -*- coding: utf-8 -*-

from typing import Union, List, Dict, Text, Any
from mock import patch

from zerver.lib.actions import try_add_realm_custom_profile_field, \
    do_update_user_custom_profile_data, do_remove_realm_custom_profile_field
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import CustomProfileField, \
    custom_profile_fields_for_realm, get_realm
import ujson

class CustomProfileFieldTest(ZulipTestCase):
    def setUp(self) -> None:
        self.original_count = len(custom_profile_fields_for_realm(get_realm("zulip").id))

    def test_list(self) -> None:
        self.login(self.example_email("iago"))
        result = self.client_get("/json/realm/profile_fields")
        self.assert_json_success(result)
        self.assertEqual(200, result.status_code)
        content = result.json()
        self.assertEqual(len(content["custom_fields"]), self.original_count)

    def test_create(self) -> None:
        self.login(self.example_email("iago"))
        data = {"name": u"Phone", "field_type": "text id"}  # type: Dict[str, Any]
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'Argument "field_type" is not valid JSON.')

        data["name"] = ""
        data["field_type"] = 100
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'Name cannot be blank.')

        data["name"] = "Phone"
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, u'Invalid field type.')

        data["name"] = "Phone"
        data["hint"] = "*" * 81
        data["field_type"] = CustomProfileField.SHORT_TEXT
        result = self.client_post("/json/realm/profile_fields", info=data)
        msg = "hint is too long (limit: 80 characters)."
        self.assert_json_error(result, msg)

        data["name"] = "Phone"
        data["hint"] = "Contact number"
        data["field_type"] = CustomProfileField.SHORT_TEXT
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result,
                               u'A field with that name already exists.')

    def test_create_choice_field(self) -> None:
        self.login(self.example_email("iago"))
        data = {}  # type: Dict[str, Union[str, int]]
        data["name"] = "Favorite programming language"
        data["field_type"] = CustomProfileField.CHOICE

        data['field_data'] = 'invalid'
        result = self.client_post("/json/realm/profile_fields", info=data)
        error_msg = "Bad value for 'field_data': invalid"
        self.assert_json_error(result, error_msg)

        data["field_data"] = ujson.dumps({
            'python': ['1'],
            'java': ['2'],
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data is not a dict')

        data["field_data"] = ujson.dumps({
            'python': {'text': 'Python'},
            'java': {'text': 'Java'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "order key is missing from field_data")

        data["field_data"] = ujson.dumps({
            'python': {'text': 'Python', 'order': ''},
            'java': {'text': 'Java', 'order': '2'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["order"] cannot be blank.')

        data["field_data"] = ujson.dumps({
            '': {'text': 'Python', 'order': '1'},
            'java': {'text': 'Java', 'order': '2'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, "'value' cannot be blank.")

        data["field_data"] = ujson.dumps({
            'python': {'text': 'Python', 'order': 1},
            'java': {'text': 'Java', 'order': '2'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_error(result, 'field_data["order"] is not a string')

        data["field_data"] = ujson.dumps({
            'python': {'text': 'Python', 'order': '1'},
            'java': {'text': 'Java', 'order': '2'},
        })
        result = self.client_post("/json/realm/profile_fields", info=data)
        self.assert_json_success(result)

    def test_not_realm_admin(self) -> None:
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/realm/profile_fields")
        self.assert_json_error(result, u'Must be an organization administrator')
        result = self.client_delete("/json/realm/profile_fields/1")
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_delete(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name="Phone number", realm=realm)
        result = self.client_delete("/json/realm/profile_fields/100")
        self.assert_json_error(result, 'Field id 100 not found.')

        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        result = self.client_delete(
            "/json/realm/profile_fields/{}".format(field.id))
        self.assert_json_success(result)
        self.assertEqual(CustomProfileField.objects.count(), self.original_count - 1)

    def test_update(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        result = self.client_patch(
            "/json/realm/profile_fields/100",
            info={'name': '',
                  'field_type': CustomProfileField.SHORT_TEXT}
        )
        self.assert_json_error(result, u'Name cannot be blank.')

        result = self.client_patch(
            "/json/realm/profile_fields/100",
            info={'name': 'Phone Number',
                  'field_type': CustomProfileField.SHORT_TEXT}
        )
        self.assert_json_error(result, u'Field id 100 not found.')

        field = CustomProfileField.objects.get(name="Phone number", realm=realm)

        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'New phone number',
                  'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_success(result)
        field = CustomProfileField.objects.get(id=field.id, realm=realm)
        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        self.assertEqual(field.name, 'New phone number')
        self.assertIs(field.hint, '')
        self.assertEqual(field.field_type, CustomProfileField.SHORT_TEXT)

        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'New phone number',
                  'hint': '*' * 81,
                  'field_type': CustomProfileField.SHORT_TEXT})
        msg = "hint is too long (limit: 80 characters)."
        self.assert_json_error(result, msg)

        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'New phone number',
                  'hint': 'New contact number',
                  'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_success(result)

        field = CustomProfileField.objects.get(id=field.id, realm=realm)
        self.assertEqual(CustomProfileField.objects.count(), self.original_count)
        self.assertEqual(field.name, 'New phone number')
        self.assertEqual(field.hint, 'New contact number')
        self.assertEqual(field.field_type, CustomProfileField.SHORT_TEXT)

        field = CustomProfileField.objects.get(name="Favorite editor", realm=realm)
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Favorite editor',
                  'field_data': 'invalid'})
        self.assert_json_error(result, "Bad value for 'field_data': invalid")

        field_data = ujson.dumps({
            'vim': 'Vim',
            'emacs': {'order': '2', 'text': 'Emacs'},
        })
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Favorite editor',
                  'field_data': field_data})
        self.assert_json_error(result, "field_data is not a dict")

        field_data = ujson.dumps({
            'vim': {'order': '1', 'text': 'Vim'},
            'emacs': {'order': '2', 'text': 'Emacs'},
            'notepad': {'order': '3', 'text': 'Notepad'},
        })
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Favorite editor',
                  'field_data': field_data})
        self.assert_json_success(result)

    def test_update_is_aware_of_uniqueness(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        try_add_realm_custom_profile_field(realm, u"Phone",
                                           CustomProfileField.SHORT_TEXT)

        field = try_add_realm_custom_profile_field(
            realm,
            u"Phone 1",
            CustomProfileField.SHORT_TEXT
        )

        self.assertEqual(CustomProfileField.objects.count(), self.original_count + 2)
        result = self.client_patch(
            "/json/realm/profile_fields/{}".format(field.id),
            info={'name': 'Phone', 'field_type': CustomProfileField.SHORT_TEXT})
        self.assert_json_error(
            result, u'A field with that name already exists.')

    def assert_error_update_invalid_value(self, field_name: str, new_value: object, error_msg: str) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name=field_name, realm=realm)

        # Update value of field
        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps([{"id": field.id, "value": new_value}])})
        self.assert_json_error(result, error_msg)

    def test_update_invalid_field(self) -> None:
        self.login(self.example_email("iago"))
        data = [{'id': 1234, 'value': '12'}]
        result = self.client_patch("/json/users/me/profile_data", {
            'data': ujson.dumps(data)
        })
        self.assert_json_error(result,
                               u"Field id 1234 not found.")

    def test_update_invalid_short_text(self) -> None:
        field_name = "Phone number"
        self.assert_error_update_invalid_value(field_name, 't' * 201,
                                               u"{} is too long (limit: 50 characters).".format(field_name))

    def test_update_invalid_date(self) -> None:
        field_name = "Birthday"
        self.assert_error_update_invalid_value(field_name, u"a-b-c",
                                               u"{} is not a date".format(field_name))
        self.assert_error_update_invalid_value(field_name, 123,
                                               u"{} is not a string".format(field_name))

    def test_update_invalid_url(self) -> None:
        field_name = "GitHub profile"
        self.assert_error_update_invalid_value(field_name, u"not URL",
                                               u"{} is not a URL".format(field_name))

    def test_update_profile_data_successfully(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        fields = [
            ('Phone number', 'short text data'),
            ('Biography', 'long text data'),
            ('Favorite food', 'short text data'),
            ('Favorite editor', 'vim'),
            ('Birthday', '1909-3-5'),
            ('GitHub profile', 'https://github.com/ABC'),
        ]

        data = []
        for i, field_value in enumerate(fields):
            name, value = field_value
            field = CustomProfileField.objects.get(name=name, realm=realm)
            data.append({
                'id': field.id,
                'value': value,
            })

        # Update value of field
        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps(data)})
        self.assert_json_success(result)

        iago = self.example_user('iago')
        expected_value = {f['id']: f['value'] for f in data}

        for field_dict in iago.profile_data:
            self.assertEqual(field_dict['value'], expected_value[field_dict['id']])
            for k in ['id', 'type', 'name', 'field_data']:
                self.assertIn(k, field_dict)

            self.assertEqual(len(iago.profile_data), self.original_count)

        # Update value of one field.
        field = CustomProfileField.objects.get(name='Biography', realm=realm)
        data = [{
            'id': field.id,
            'value': 'foobar',
        }]

        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps(data)})
        self.assert_json_success(result)
        for f in iago.profile_data:
            if f['id'] == field.id:
                self.assertEqual(f['value'], 'foobar')

    def test_update_invalid_choice_field(self) -> None:
        field_name = "Favorite editor"
        self.assert_error_update_invalid_value(field_name, "foobar",
                                               "'foobar' is not a valid choice for '{}'.".format(field_name))

    def test_update_choice_field_successfully(self) -> None:
        self.login(self.example_email("iago"))
        realm = get_realm('zulip')
        field = CustomProfileField.objects.get(name='Favorite editor', realm=realm)
        data = [{
            'id': field.id,
            'value': 'emacs',
        }]

        result = self.client_patch("/json/users/me/profile_data",
                                   {'data': ujson.dumps(data)})
        self.assert_json_success(result)

    def test_delete_internals(self) -> None:
        user_profile = self.example_user('iago')
        realm = user_profile.realm
        field = CustomProfileField.objects.get(name="Phone number", realm=realm)
        data = [{'id': field.id, 'value': u'123456'}]  # type: List[Dict[str, Union[int, Text]]]
        do_update_user_custom_profile_data(user_profile, data)

        self.assertEqual(len(custom_profile_fields_for_realm(realm.id)), self.original_count)
        self.assertEqual(user_profile.customprofilefieldvalue_set.count(), self.original_count)

        do_remove_realm_custom_profile_field(realm, field)

        self.assertEqual(len(custom_profile_fields_for_realm(realm.id)), self.original_count - 1)
        self.assertEqual(user_profile.customprofilefieldvalue_set.count(), self.original_count - 1)
