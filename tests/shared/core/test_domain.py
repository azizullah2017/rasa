import copy
import json
import textwrap
from pathlib import Path
import random
from typing import Dict, List, Text, Any, Union, Set, Optional

import pytest

from rasa.shared.exceptions import YamlSyntaxException, YamlException
import rasa.shared.utils.io
from rasa.shared.constants import (
    DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES,
    LATEST_TRAINING_DATA_FORMAT_VERSION,
    IGNORED_INTENTS,
)
from rasa.core import training
from rasa.core.featurizers.tracker_featurizers import MaxHistoryTrackerFeaturizer
from rasa.shared.core.slots import InvalidSlotTypeException, TextSlot
from rasa.shared.core.constants import (
    DEFAULT_INTENTS,
    SLOT_LISTED_ITEMS,
    SLOT_LAST_OBJECT,
    SLOT_LAST_OBJECT_TYPE,
    DEFAULT_KNOWLEDGE_BASE_ACTION,
    ENTITY_LABEL_SEPARATOR,
    DEFAULT_ACTION_NAMES,
)
from rasa.shared.core.domain import (
    InvalidDomain,
    SessionConfig,
    ENTITY_ROLES_KEY,
    USED_ENTITIES_KEY,
    USE_ENTITIES_KEY,
    IGNORE_ENTITIES_KEY,
    State,
    Domain,
    KEY_FORMS,
    KEY_E2E_ACTIONS,
    KEY_INTENTS,
    KEY_ENTITIES,
    KEY_SLOTS,
)
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.core.events import ActionExecuted, SlotSet, UserUttered
from rasa.shared.utils.validation import YamlValidationException


def test_slots_states_before_user_utterance(domain: Domain):
    featurizer = MaxHistoryTrackerFeaturizer()
    tracker = DialogueStateTracker.from_events(
        "bla",
        evts=[
            SlotSet(domain.slots[0].name, "some_value"),
            ActionExecuted("utter_default"),
        ],
        slots=domain.slots,
    )
    trackers_as_states, _ = featurizer.training_states_and_labels([tracker], domain)
    expected_states = [[{"slots": {"name": (1.0,)}}]]
    assert trackers_as_states == expected_states


def test_create_train_data_no_history(domain: Domain, stories_path: Text):
    featurizer = MaxHistoryTrackerFeaturizer(max_history=1)
    training_trackers = training.load_data(stories_path, domain, augmentation_factor=0)

    assert len(training_trackers) == 4
    (decoded, _) = featurizer.training_states_and_labels(training_trackers, domain)

    # decoded needs to be sorted
    hashed = []
    for states in decoded:
        hashed.append(json.dumps(states, sort_keys=True))
    hashed = sorted(hashed, reverse=True)

    assert hashed == [
        "[{}]",
        '[{"prev_action": {"action_name": "utter_greet"}, "user": {"intent": "greet"}}]',
        '[{"prev_action": {"action_name": "utter_greet"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}]',
        '[{"prev_action": {"action_name": "utter_goodbye"}, "user": {"intent": "goodbye"}}]',
        '[{"prev_action": {"action_name": "utter_default"}, "user": {"intent": "default"}}]',
        '[{"prev_action": {"action_name": "utter_default"}, "slots": {"name": [1.0]}, "user": {"intent": "default"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "greet"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "goodbye"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "default"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "slots": {"name": [1.0]}, "user": {"intent": "default"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}]',
    ]


def test_create_train_data_with_history(domain: Domain, stories_path: Text):
    featurizer = MaxHistoryTrackerFeaturizer(max_history=4)
    training_trackers = training.load_data(stories_path, domain, augmentation_factor=0)
    assert len(training_trackers) == 4
    (decoded, _) = featurizer.training_states_and_labels(training_trackers, domain)

    # decoded needs to be sorted
    hashed = []
    for states in decoded:
        hashed.append(json.dumps(states, sort_keys=True))
    hashed = sorted(hashed)

    assert hashed == [
        '[{"prev_action": {"action_name": "action_listen"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}, {"prev_action": {"action_name": "utter_greet"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}, {"prev_action": {"action_name": "action_listen"}, "slots": {"name": [1.0]}, "user": {"intent": "default"}}, {"prev_action": {"action_name": "utter_default"}, "slots": {"name": [1.0]}, "user": {"intent": "default"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "default"}}, {"prev_action": {"action_name": "utter_default"}, "user": {"intent": "default"}}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "goodbye"}}, {"prev_action": {"action_name": "utter_goodbye"}, "user": {"intent": "goodbye"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "greet"}}, {"prev_action": {"action_name": "utter_greet"}, "user": {"intent": "greet"}}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "default"}}, {"prev_action": {"action_name": "utter_default"}, "user": {"intent": "default"}}]',
        '[{"prev_action": {"action_name": "utter_greet"}, "user": {"intent": "greet"}}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "default"}}, {"prev_action": {"action_name": "utter_default"}, "user": {"intent": "default"}}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "goodbye"}}]',
        '[{}, {"prev_action": {"action_name": "action_listen"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}, {"prev_action": {"action_name": "utter_greet"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}, {"prev_action": {"action_name": "action_listen"}, "slots": {"name": [1.0]}, "user": {"intent": "default"}}]',
        '[{}, {"prev_action": {"action_name": "action_listen"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}, {"prev_action": {"action_name": "utter_greet"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}]',
        '[{}, {"prev_action": {"action_name": "action_listen"}, "slots": {"name": [1.0]}, "user": {"entities": ["name"], "intent": "greet"}}]',
        '[{}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "goodbye"}}, {"prev_action": {"action_name": "utter_goodbye"}, "user": {"intent": "goodbye"}}]',
        '[{}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "goodbye"}}]',
        '[{}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "greet"}}, {"prev_action": {"action_name": "utter_greet"}, "user": {"intent": "greet"}}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "default"}}]',
        '[{}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "greet"}}, {"prev_action": {"action_name": "utter_greet"}, "user": {"intent": "greet"}}]',
        '[{}, {"prev_action": {"action_name": "action_listen"}, "user": {"intent": "greet"}}]',
        "[{}]",
    ]


def check_for_too_many_entities_and_remove_them(state: State) -> State:
    # we ignore entities where there are > 1 of them:
    # entities come from dictionary keys; as a result, they are stored
    # in different order in the tuple which makes the test unstable
    if (
        state.get("user")
        and state.get("user", {}).get("entities")
        and len(state.get("user").get("entities")) > 1
    ):
        state.get("user")["entities"] = ()
    return state


def test_create_train_data_unfeaturized_entities():
    domain_file = "data/test_domains/default_unfeaturized_entities.yml"
    stories_file = "data/test_yaml_stories/stories_unfeaturized_entities.yml"
    domain = Domain.load(domain_file)
    featurizer = MaxHistoryTrackerFeaturizer(max_history=1)
    training_trackers = training.load_data(stories_file, domain, augmentation_factor=0)

    assert len(training_trackers) == 2
    (decoded, _) = featurizer.training_states_and_labels(training_trackers, domain)

    # decoded needs to be sorted
    hashed = []
    for states in decoded:
        new_states = [
            check_for_too_many_entities_and_remove_them(state) for state in states
        ]

        hashed.append(json.dumps(new_states, sort_keys=True))
    hashed = sorted(hashed, reverse=True)

    assert hashed == [
        "[{}]",
        '[{"prev_action": {"action_name": "utter_greet"}, "user": {"intent": "greet"}}]',
        '[{"prev_action": {"action_name": "utter_greet"}, "user": {"entities": ["name"], "intent": "greet"}}]',
        '[{"prev_action": {"action_name": "utter_goodbye"}, "user": {"intent": "goodbye"}}]',
        '[{"prev_action": {"action_name": "utter_default"}, "user": {"intent": "why"}}]',
        '[{"prev_action": {"action_name": "utter_default"}, "user": {"intent": "thank"}}]',
        '[{"prev_action": {"action_name": "utter_default"}, "user": {"entities": [], "intent": "default"}}]',
        '[{"prev_action": {"action_name": "utter_default"}, "user": {"entities": [], "intent": "ask"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "why"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "thank"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "greet"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"intent": "goodbye"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"entities": [], "intent": "default"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"entities": [], "intent": "ask"}}]',
        '[{"prev_action": {"action_name": "action_listen"}, "user": {"entities": ["name"], "intent": "greet"}}]',
    ]


def test_domain_from_template(domain: Domain):
    assert not domain.is_empty()
    assert len(domain.intents) == 10 + len(DEFAULT_INTENTS)
    assert len(domain.action_names_or_texts) == 18


def test_avoid_action_repetition(domain: Domain):
    domain = Domain.from_yaml(
        """
        version: "3.0"
        actions:
        - utter_greet
        responses:
            utter_greet:
            - text: "hi"
        """
    )

    assert len(domain.action_names_or_texts) == len(DEFAULT_ACTION_NAMES) + 1


def test_custom_slot_type(tmpdir: Path):
    domain_path = str(tmpdir / "domain.yml")
    rasa.shared.utils.io.write_text_file(
        """
       slots:
         custom:
           type: tests.core.conftest.CustomSlot
           mappings:
           - type: from_text

       responses:
         utter_greet:
           - text: hey there! """,
        domain_path,
    )
    Domain.load(domain_path)


@pytest.mark.parametrize(
    "domain_unkown_slot_type",
    [
        """
    slots:
        custom:
         type: tests.core.conftest.Unknown
         mappings:
         - type: from_text

    responses:
        utter_greet:
         - text: hey there!""",
        """
    slots:
        custom:
         type: blubblubblub
         mappings:
         - type: from_text

    responses:
        utter_greet:
         - text: hey there!""",
    ],
)
def test_domain_fails_on_unknown_custom_slot_type(tmpdir, domain_unkown_slot_type):
    domain_path = str(tmpdir / "domain.yml")
    rasa.shared.utils.io.write_text_file(domain_unkown_slot_type, domain_path)
    with pytest.raises(InvalidSlotTypeException):
        Domain.load(domain_path)


def test_domain_to_dict():
    test_yaml = textwrap.dedent(
        f"""
    actions:
    - action_save_world
    config:
      store_entities_as_slots: true
    entities: []
    forms:
      some_form:
       required_slots: []
    intents: []
    responses:
      utter_greet:
      - text: hey there!
    session_config:
      carry_over_slots_to_new_session: true
      session_expiration_time: 60
    {KEY_E2E_ACTIONS}:
    - Hello, dear user
    - what's up
    slots:
      some_slot:
        type: categorical
        values:
        - high
        - low
        mappings:
        - type: from_text"""
    )

    domain_as_dict = Domain.from_yaml(test_yaml).as_dict()

    assert domain_as_dict == {
        "actions": ["action_save_world"],
        "config": {"store_entities_as_slots": True},
        KEY_E2E_ACTIONS: ["Hello, dear user", "what's up"],
        "entities": [],
        "forms": {"some_form": {"required_slots": []}},
        "intents": [],
        "responses": {"utter_greet": [{"text": "hey there!"}]},
        "session_config": {
            "carry_over_slots_to_new_session": True,
            "session_expiration_time": 60,
        },
        "slots": {
            "some_slot": {
                "values": ["high", "low"],
                "influence_conversation": True,
                "initial_value": None,
                "mappings": [{"type": "from_text"}],
                "type": "rasa.shared.core.slots.CategoricalSlot",
            }
        },
    }


def test_domain_to_yaml():
    test_yaml = f"""
version: '3.0'
actions:
- action_save_world
config:
  store_entities_as_slots: true
e2e_actions: []
entities: []
forms: {{}}
intents: []
responses:
  utter_greet:
  - text: hey there!
session_config:
  carry_over_slots_to_new_session: true
  session_expiration_time: {DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES}
slots: {{}}
"""

    with pytest.warns(UserWarning) as record:
        domain = Domain.from_yaml(test_yaml)
        actual_yaml = domain.as_yaml()

    assert (
        "Slot auto-fill has been removed in 3.0"
        " and replaced with a new explicit mechanism to set slots. "
        in record[0].message.args[0]
    )

    expected = rasa.shared.utils.io.read_yaml(test_yaml)
    actual = rasa.shared.utils.io.read_yaml(actual_yaml)
    assert actual == expected


def test_merge_yaml_domains():
    test_yaml_1 = f"""config:
  store_entities_as_slots: true
entities: []
intents: []
slots: {{}}
responses:
  utter_greet:
  - text: hey there!
{KEY_E2E_ACTIONS}:
- Hi"""

    test_yaml_2 = f"""config:
  store_entities_as_slots: false
session_config:
    session_expiration_time: 20
    carry_over_slots: true
entities:
- cuisine
intents:
- greet
slots:
  cuisine:
    type: text
    mappings:
    - type: from_text
{KEY_E2E_ACTIONS}:
- Bye
responses:
  utter_goodbye:
  - text: bye!
  utter_greet:
  - text: hey you!"""

    domain_1 = Domain.from_yaml(test_yaml_1)
    domain_2 = Domain.from_yaml(test_yaml_2)
    domain = domain_1.merge(domain_2)
    # single attribute should be taken from domain_1
    assert domain.store_entities_as_slots
    # conflicts should be taken from domain_1
    assert domain.responses == {
        "utter_greet": [{"text": "hey there!"}],
        "utter_goodbye": [{"text": "bye!"}],
    }
    # lists should be deduplicated and merged
    assert domain.intents == sorted(["greet", *DEFAULT_INTENTS])
    assert domain.entities == ["cuisine"]
    assert isinstance(domain.slots[0], TextSlot)
    assert domain.slots[0].name == "cuisine"
    assert sorted(domain.user_actions) == sorted(["utter_greet", "utter_goodbye"])
    assert domain.session_config == SessionConfig(20, True)

    domain = domain_1.merge(domain_2, override=True)
    # single attribute should be taken from domain_2
    assert not domain.store_entities_as_slots
    # conflicts should take value from domain_2
    assert domain.responses == {
        "utter_greet": [{"text": "hey you!"}],
        "utter_goodbye": [{"text": "bye!"}],
    }
    assert domain.session_config == SessionConfig(20, True)
    assert domain.action_texts == ["Bye", "Hi"]


@pytest.mark.parametrize("default_intent", DEFAULT_INTENTS)
def test_merge_yaml_domains_with_default_intents(default_intent: Text):
    test_yaml_1 = """intents: []"""

    # this domain contains an overridden default intent
    test_yaml_2 = f"""intents:
- greet
- {default_intent}"""

    domain_1 = Domain.from_yaml(test_yaml_1)
    domain_2 = Domain.from_yaml(test_yaml_2)
    domain = domain_1.merge(domain_2)

    # check that the default intents were merged correctly
    assert default_intent in domain.intents
    assert domain.intents == sorted(["greet", *DEFAULT_INTENTS])

    # ensure that the default intent is contain the domain's dictionary dump
    domain_intents = []
    for intent in domain.as_dict()["intents"]:
        domain_intents.append(list(intent)[0])

    assert default_intent in domain_intents


def test_merge_session_config_if_first_is_not_default():
    yaml1 = """
session_config:
    session_expiration_time: 20
    carry_over_slots: true"""

    yaml2 = """
 session_config:
    session_expiration_time: 40
    carry_over_slots: true
    """

    domain1 = Domain.from_yaml(yaml1)
    domain2 = Domain.from_yaml(yaml2)

    merged = domain1.merge(domain2)
    assert merged.session_config == SessionConfig(20, True)

    merged = domain1.merge(domain2, override=True)
    assert merged.session_config == SessionConfig(40, True)


def test_merge_with_empty_domain():
    domain = Domain.from_yaml(
        """
        version: "3.0"
        config:
          store_entities_as_slots: false
        session_config:
            session_expiration_time: 20
            carry_over_slots: true
        entities:
        - cuisine
        intents:
        - greet
        slots:
          cuisine:
            type: text
            mappings:
            - type: from_text
        responses:
          utter_goodbye:
          - text: bye!
          utter_greet:
          - text: hey you!
        """
    )

    merged = Domain.empty().merge(domain)

    assert merged.as_dict() == domain.as_dict()


@pytest.mark.parametrize("other", [Domain.empty(), None])
def test_merge_with_empty_other_domain(other: Optional[Domain]):
    domain = Domain.from_yaml(
        """
        version: "3.0"
        config:
          store_entities_as_slots: false
        session_config:
            session_expiration_time: 20
            carry_over_slots: true
        entities:
        - cuisine
        intents:
        - greet
        slots:
          cuisine:
            type: text
            mappings:
            - type: from_text
        responses:
          utter_goodbye:
          - text: bye!
          utter_greet:
          - text: hey you!
        """
    )

    merged = domain.merge(other, override=True)

    assert merged.as_dict() == domain.as_dict()


def test_merge_domain_with_forms():
    test_yaml_1 = """
    slots:
      slot1:
        type: text
        mappings:
        - type: from_text
    forms:
      my_form:
        required_slots:
            - slot1

      my_form2:
        required_slots: []
    """

    test_yaml_2 = """
    slots:
      slot1:
        type: text
        mappings:
        - type: from_text
    forms:
      my_form3:
        required_slots:
          - slot1
    """

    domain_1 = Domain.from_yaml(test_yaml_1)
    domain_2 = Domain.from_yaml(test_yaml_2)
    domain = domain_1.merge(domain_2)

    expected_number_of_forms = 3
    assert len(domain.form_names) == expected_number_of_forms
    assert len(domain.forms) == expected_number_of_forms


@pytest.mark.parametrize(
    "intents, entities, roles, groups, intent_properties",
    [
        (
            ["greet", "goodbye"],
            ["entity", "other", "third"],
            {"entity": ["role-1", "role-2"]},
            {},
            {
                "greet": {
                    USED_ENTITIES_KEY: [
                        "entity",
                        f"entity{ENTITY_LABEL_SEPARATOR}role-1",
                        f"entity{ENTITY_LABEL_SEPARATOR}role-2",
                        "other",
                        "third",
                    ]
                },
                "goodbye": {
                    USED_ENTITIES_KEY: [
                        "entity",
                        f"entity{ENTITY_LABEL_SEPARATOR}role-1",
                        f"entity{ENTITY_LABEL_SEPARATOR}role-2",
                        "other",
                        "third",
                    ]
                },
            },
        ),
        (
            [{"greet": {USE_ENTITIES_KEY: []}}, "goodbye"],
            ["entity", "other", "third"],
            {},
            {"other": ["1", "2"]},
            {
                "greet": {USED_ENTITIES_KEY: []},
                "goodbye": {
                    USED_ENTITIES_KEY: [
                        "entity",
                        "other",
                        f"other{ENTITY_LABEL_SEPARATOR}1",
                        f"other{ENTITY_LABEL_SEPARATOR}2",
                        "third",
                    ]
                },
            },
        ),
        (
            [
                {
                    "greet": {
                        "triggers": "utter_goodbye",
                        USE_ENTITIES_KEY: ["entity"],
                        IGNORE_ENTITIES_KEY: ["other"],
                    }
                },
                "goodbye",
            ],
            ["entity", "other", "third"],
            {"entity": ["role"], "other": ["role"]},
            {},
            {
                "greet": {
                    "triggers": "utter_goodbye",
                    USED_ENTITIES_KEY: [
                        "entity",
                        f"entity{ENTITY_LABEL_SEPARATOR}role",
                    ],
                },
                "goodbye": {
                    USED_ENTITIES_KEY: [
                        "entity",
                        f"entity{ENTITY_LABEL_SEPARATOR}role",
                        "other",
                        f"other{ENTITY_LABEL_SEPARATOR}role",
                        "third",
                    ]
                },
            },
        ),
        (
            [
                {"greet": {"triggers": "utter_goodbye", USE_ENTITIES_KEY: None}},
                {"goodbye": {USE_ENTITIES_KEY: [], IGNORE_ENTITIES_KEY: []}},
            ],
            ["entity", "other", "third"],
            {},
            {},
            {
                "greet": {USED_ENTITIES_KEY: [], "triggers": "utter_goodbye"},
                "goodbye": {USED_ENTITIES_KEY: []},
            },
        ),
        (
            [
                "greet",
                "goodbye",
                {"chitchat": {"is_retrieval_intent": True, "use_entities": None}},
            ],
            ["entity", "other", "third"],
            {},
            {},
            {
                "greet": {USED_ENTITIES_KEY: ["entity", "other", "third"]},
                "goodbye": {USED_ENTITIES_KEY: ["entity", "other", "third"]},
                "chitchat": {USED_ENTITIES_KEY: [], "is_retrieval_intent": True},
            },
        ),
    ],
)
def test_collect_intent_properties(
    intents: Union[Set[Text], List[Union[Text, Dict[Text, Any]]]],
    entities: List[Text],
    roles: Dict[Text, List[Text]],
    groups: Dict[Text, List[Text]],
    intent_properties: Dict[Text, Dict[Text, Union[bool, List]]],
):
    Domain._add_default_intents(intent_properties, entities, roles, groups)

    assert (
        Domain.collect_intent_properties(intents, entities, roles, groups)
        == intent_properties
    )


def test_load_domain_from_directory_tree():
    domain_path = "data/test_domains/test_domain_from_directory_tree"

    actual = Domain.load(domain_path)
    expected_intents = [
        "utter_root",
        "utter_root2",
        "utter_skill_1",
        "utter_skill_2",
        "utter_subskill",
    ]
    expected_entities = [
        "ball",
        "chess",
        "monopoly",
        "cluedo",
        "pandemic",
    ]
    expected_responses = {
        "utter_greet": [{"text": "Hey! How are you?"}],
        "utter_cheer_up": [
            {
                "text": "Here is something to cheer you up:",
                "image": "https://i.imgur.com/nGF1K8f.jpg",
            }
        ],
    }
    assert set(expected_intents).issubset(set(actual.intents))
    assert set(expected_entities) == (set(actual.entities))
    assert set(expected_responses) == (set(actual.responses))


def test_domain_from_multiple_files():
    domain_path = "data/test_domains/test_domain_from_multiple_files"
    domain = Domain.load(domain_path)

    expected_intents = [
        "affirm",
        "are_you_there",
        "back",
        "bot_challenge",
        "cure_network",
        "delay",
        "deny",
        "device_selection_scaffold",
        "drum_clocks",
        "drum_lampshades",
        "drum_robot",
        "drum_robot_chocolate",
        "drum_soups",
        "drum_wallets",
        "endless_love",
        "exchange_wallet",
        "finish_humble_selection",
        "finish_selection",
        "finish_selection_line",
        "greeting",
        "humble_selection",
        "humble_selection_scaffold",
        "main_menu",
        "nlu_fallback",
        "open_wallet",
        "out_of_scope",
        "profanity",
        "restart",
        "run_finish",
        "run_finish_recent",
        "run_finished",
        "selection_troubleshooting",
        "self_selection",
        "session_start",
        "thanks",
        "unsure_selection_scaffold",
        "view_offers",
    ]
    expected_entities = [
        "caramel_robot",
        "chocolate_robot",
        "other_robot",
        "pistachio_robot",
        "rum_and_raisin_robot",
        "strawberry_robot",
        "vanilla_robot",
    ]
    expected_actions = [
        "action_increase_15",
        "action_prevent_20",
        "action_utter_cure_standard",
        "action_utter_drum_menu",
        "action_utter_main_menu",
        "action_utter_previous_message",
        "action_utter_robot_menu",
        "action_utter_smalltalk_greeting",
        "utter_anythingelse_menu",
        "utter_bot_challenge",
        "utter_cure_specific",
        "utter_cure_standard",
        "utter_drumclocks",
        "utter_drumlampshades",
        "utter_drumsoups",
        "utter_drumwallets",
        "utter_finish_humble_selection",
        "utter_finish_selection",
        "utter_finish_selection_line",
        "utter_greengrey_wallet",
        "utter_horn_selection_scaffold",
        "utter_humble_selection",
        "utter_humble_selection_scaffold",
        "utter_im_here",
        "utter_non_standard",
        "utter_open_wallet_options",
        "utter_profanity",
        "utter_run_finish",
        "utter_run_finish_recent",
        "utter_run_finished",
        "utter_selection_issues",
        "utter_smalltalk_greeting",
        "utter_std_drum_menu",
        "utter_thanks_response",
        "utter_tmo_love",
        "utter_amazement",
        "utter_default",
        "utter_goodbye",
        "utter_greet",
    ]
    expected_forms = {
        "robot_form": {"required_slots": ["propose_simulation", "display_cure_method"]}
    }
    expected_responses = {
        "utter_greet": [{"text": "hey there!"}],
        "utter_goodbye": [{"text": "goodbye :("}],
        "utter_default": [{"text": "default message"}],
        "utter_amazement": [{"text": "awesomness!"}],
    }
    expected_slots = [
        "activate_double_simulation",
        "activate_simulation",
        "display_cure_method",
        "display_drum_cure_horns",
        "display_method_artwork",
        "drumAllClocks",
        "drumAllLampshades",
        "drumAllSoups",
        "drumChocolateWallets",
        "drumClockAdapters",
        "drumClockCovers",
        "drumClocksChocolate",
        "drumClocksStrawberry",
        "drumMindspace",
        "drumOtherWallets",
        "drumSnareWallets",
        "drumSoupChocolate",
        "drumSoupStrawberry",
        "drumStrawberryWallets",
        "greenOrGrey",
        "humbleSelection",
        "humbleSelectionManagement",
        "humbleSelectionStatus",
        "offers",
        "requested_slot",
        "session_started_metadata",
    ]

    domain_slots = []

    for slot in domain.slots:
        domain_slots.append(slot.name)

    assert expected_intents == domain.intents
    assert expected_entities == domain.entities
    assert expected_actions == domain.user_actions
    assert expected_responses == domain.responses
    assert expected_forms == domain.forms
    assert domain.session_config.session_expiration_time == 360
    assert expected_slots == sorted(domain_slots)


def test_domain_warnings(domain: Domain):
    warning_types = [
        "action_warnings",
        "intent_warnings",
        "entity_warnings",
        "slot_warnings",
    ]

    actions = ["action_1", "action_2"]
    intents = ["intent_1", "intent_2"]
    entities = ["entity_1", "entity_2"]
    slots = ["slot_1", "slot_2"]
    domain_warnings = domain.domain_warnings(
        intents=intents, entities=entities, actions=actions, slots=slots
    )

    # elements not found in domain should be in `in_training_data` diff
    for _type, elements in zip(warning_types, [actions, intents, entities]):
        assert set(domain_warnings[_type]["in_training_data"]) == set(elements)

    # all other domain elements should be in `in_domain` diff
    for _type, elements in zip(
        warning_types,
        [domain.user_actions + domain.form_names, domain.intents, domain.entities],
    ):
        assert set(domain_warnings[_type]["in_domain"]) == set(elements)

    # fully aligned domain and elements should yield empty diff
    domain_warnings = domain.domain_warnings(
        intents=domain.intents,
        entities=domain.entities,
        actions=domain.user_actions + domain.form_names,
        slots=[s.name for s in domain._user_slots],
    )

    for diff_dict in domain_warnings.values():
        assert all(not diff_set for diff_set in diff_dict.values())


def test_unfeaturized_slot_in_domain_warnings():
    # create empty domain
    featurized_slot_name = "text_slot"
    unfeaturized_slot_name = "unfeaturized_slot"
    domain = Domain.from_dict(
        {
            "slots": {
                featurized_slot_name: {
                    "initial_value": "value2",
                    "type": "text",
                    "mappings": [{"type": "from_text"}],
                },
                unfeaturized_slot_name: {
                    "type": "text",
                    "initial_value": "value1",
                    "influence_conversation": False,
                    "mappings": [{"type": "from_text"}],
                },
            }
        }
    )

    # ensure both are in domain
    for slot in (featurized_slot_name, unfeaturized_slot_name):
        assert slot in [slot.name for slot in domain.slots]

    # text slot should appear in domain warnings, unfeaturized slot should not
    in_domain_slot_warnings = domain.domain_warnings()["slot_warnings"]["in_domain"]
    assert featurized_slot_name in in_domain_slot_warnings
    assert unfeaturized_slot_name not in in_domain_slot_warnings


def test_check_domain_sanity_on_invalid_domain():
    with pytest.raises(InvalidDomain):
        Domain(
            intents={},
            entities=[],
            slots=[],
            responses={},
            action_names=["random_name", "random_name"],
            forms={},
        )

    with pytest.raises(InvalidDomain):
        Domain(
            intents={},
            entities=[],
            slots=[
                TextSlot("random_name", mappings=[{}]),
                TextSlot("random_name", mappings=[{}]),
            ],
            responses={},
            action_names=[],
            forms={},
        )

    with pytest.raises(InvalidDomain):
        Domain(
            intents={},
            entities=["random_name", "random_name", "other_name", "other_name"],
            slots=[],
            responses={},
            action_names=[],
            forms={},
        )


def test_load_on_invalid_domain_duplicate_intents():
    with pytest.raises(InvalidDomain):
        Domain.load("data/test_domains/duplicate_intents.yml")


def test_load_on_invalid_domain_duplicate_actions():
    with pytest.raises(InvalidDomain):
        Domain.load("data/test_domains/duplicate_actions.yml")


def test_schema_error_with_forms_as_lists():
    with pytest.raises(YamlException):
        Domain.from_yaml(
            """
        version: '3.0'
        forms: []
        """
        )


def test_schema_error_with_forms_and_slots_but_without_required_slots_key():
    with pytest.raises(YamlException):
        Domain.from_yaml(
            """
        version: '3.0'
        forms:
          my_form:
            cool_slot:
            - type: from_text
        """
        )


def test_load_on_invalid_domain_duplicate_responses():
    with pytest.raises(YamlSyntaxException):
        Domain.load("data/test_domains/duplicate_responses.yml")


def test_load_on_invalid_domain_duplicate_entities():
    with pytest.raises(InvalidDomain):
        Domain.load("data/test_domains/duplicate_entities.yml")


def test_load_domain_with_entity_roles_groups():
    domain = Domain.load("data/test_domains/travel_form.yml")

    assert domain.entities is not None
    assert "GPE" in domain.entities
    assert "name" in domain.entities
    assert "name" not in domain.roles
    assert "GPE" in domain.roles
    assert "origin" in domain.roles["GPE"]
    assert "destination" in domain.roles["GPE"]


def test_is_empty():
    assert Domain.empty().is_empty()


def test_transform_intents_for_file_default():
    domain_path = "data/test_domains/default_unfeaturized_entities.yml"
    domain = Domain.load(domain_path)
    transformed = domain._transform_intents_for_file()

    expected = [
        {"ask": {USE_ENTITIES_KEY: True}},
        {"default": {IGNORE_ENTITIES_KEY: ["unrelated_recognized_entity"]}},
        {"goodbye": {USE_ENTITIES_KEY: []}},
        {"greet": {USE_ENTITIES_KEY: ["name"]}},
        {"pure_intent": {USE_ENTITIES_KEY: True}},
        {"thank": {USE_ENTITIES_KEY: []}},
        {"why": {USE_ENTITIES_KEY: []}},
    ]

    assert transformed == expected


def test_transform_intents_for_files_with_entities():
    domain_path = "data/test_domains/test_domain_from_directory_for_entities"
    domain = Domain.load(domain_path)
    transformed = domain._transform_intents_for_file()

    expected = [
        {"certify": {USE_ENTITIES_KEY: True}},
        {"play": {USE_ENTITIES_KEY: ["ball", "chess"]}},
        {"question": {USE_ENTITIES_KEY: True}},
        {"stow_away": {USE_ENTITIES_KEY: True}},
        {
            "support_encouraging": {
                USE_ENTITIES_KEY: ["anti_freeze_blankets", "automatic_cupcakes"]
            }
        },
        {"vacationing": {"ignore_entities": ["tornadoes"]}},
    ]

    assert transformed == expected


def test_transform_intents_for_file_with_mapping():
    domain_path = "data/test_domains/default_with_mapping.yml"
    domain = Domain.load(domain_path)
    transformed = domain._transform_intents_for_file()

    expected = [
        {"default": {"triggers": "utter_default", USE_ENTITIES_KEY: True}},
        {"goodbye": {USE_ENTITIES_KEY: True}},
        {"greet": {"triggers": "utter_greet", USE_ENTITIES_KEY: True}},
    ]

    assert transformed == expected


def test_transform_intents_for_file_with_entity_roles_groups():
    domain_path = "data/test_domains/travel_form.yml"
    domain = Domain.load(domain_path)
    transformed = domain._transform_intents_for_file()

    expected = [
        {"greet": {USE_ENTITIES_KEY: ["name"]}},
        {"inform": {USE_ENTITIES_KEY: ["GPE"]}},
    ]

    assert transformed == expected


def test_transform_entities_for_file_default():
    domain_path = "data/test_domains/travel_form.yml"
    domain = Domain.load(domain_path)
    transformed = domain._transform_entities_for_file()

    expected = [{"GPE": {ENTITY_ROLES_KEY: ["destination", "origin"]}}, "name"]

    assert transformed == expected


def test_clean_domain_for_file():
    domain_path = "data/test_domains/default_unfeaturized_entities.yml"
    cleaned = Domain.load(domain_path).cleaned_domain()

    expected = {
        "entities": ["name", "unrelated_recognized_entity", "other"],
        "intents": [
            "ask",
            {"default": {IGNORE_ENTITIES_KEY: ["unrelated_recognized_entity"]}},
            {"goodbye": {USE_ENTITIES_KEY: []}},
            {"greet": {USE_ENTITIES_KEY: ["name"]}},
            "pure_intent",
            {"thank": {USE_ENTITIES_KEY: []}},
            {"why": {USE_ENTITIES_KEY: []}},
        ],
        "responses": {
            "utter_default": [{"text": "default message"}],
            "utter_goodbye": [{"text": "goodbye :("}],
            "utter_greet": [{"text": "hey there!"}],
        },
        "session_config": {
            "carry_over_slots_to_new_session": True,
            "session_expiration_time": DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES,
        },
    }

    assert cleaned == expected


def test_not_add_knowledge_base_slots():
    test_domain = Domain.empty()

    slot_names = [s.name for s in test_domain.slots]

    assert SLOT_LISTED_ITEMS not in slot_names
    assert SLOT_LAST_OBJECT not in slot_names
    assert SLOT_LAST_OBJECT_TYPE not in slot_names


def test_add_knowledge_base_slots():
    test_domain = Domain.from_yaml(
        f"""
        version: "3.0"
        actions:
        - {DEFAULT_KNOWLEDGE_BASE_ACTION}
        """
    )

    slot_names = [s.name for s in test_domain.slots]

    assert SLOT_LISTED_ITEMS in slot_names
    assert SLOT_LAST_OBJECT in slot_names
    assert SLOT_LAST_OBJECT_TYPE in slot_names


@pytest.mark.parametrize(
    "input_domain, expected_session_expiration_time, expected_carry_over_slots",
    [
        (
            f"""session_config:
    session_expiration_time: {DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES}
    carry_over_slots_to_new_session: true""",
            DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES,
            True,
        ),
        ("", DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES, True),
        (
            """session_config:
        carry_over_slots_to_new_session: false""",
            DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES,
            False,
        ),
        (
            """session_config:
        session_expiration_time: 20.2
        carry_over_slots_to_new_session: False""",
            20.2,
            False,
        ),
        ("""session_config: {}""", DEFAULT_SESSION_EXPIRATION_TIME_IN_MINUTES, True),
    ],
)
def test_session_config(
    input_domain,
    expected_session_expiration_time: float,
    expected_carry_over_slots: bool,
):
    domain = Domain.from_yaml(input_domain)
    assert (
        domain.session_config.session_expiration_time
        == expected_session_expiration_time
    )
    assert domain.session_config.carry_over_slots == expected_carry_over_slots


def test_domain_as_dict_with_session_config():
    session_config = SessionConfig(123, False)
    domain = Domain.empty()
    domain.session_config = session_config

    serialized = domain.as_dict()
    deserialized = Domain.from_dict(serialized)

    assert deserialized.session_config == session_config


@pytest.mark.parametrize(
    "session_config, enabled",
    [
        (SessionConfig(0, True), False),
        (SessionConfig(1, True), True),
        (SessionConfig(-1, False), False),
    ],
)
def test_are_sessions_enabled(session_config: SessionConfig, enabled: bool):
    assert session_config.are_sessions_enabled() == enabled


def test_domain_from_dict_does_not_change_input():
    input_before = {
        "intents": [
            {"greet": {USE_ENTITIES_KEY: ["name"]}},
            {"default": {IGNORE_ENTITIES_KEY: ["unrelated_recognized_entity"]}},
            {"goodbye": {USE_ENTITIES_KEY: None}},
            {"thank": {USE_ENTITIES_KEY: False}},
            {"ask": {USE_ENTITIES_KEY: True}},
            {"why": {USE_ENTITIES_KEY: []}},
            "pure_intent",
        ],
        "entities": ["name", "unrelated_recognized_entity", "other"],
        "slots": {"name": {"type": "text", "mappings": [{"type": "from_text"}]}},
        "responses": {
            "utter_greet": [{"text": "hey there {name}!"}],
            "utter_goodbye": [{"text": "goodbye 😢"}, {"text": "bye bye 😢"}],
            "utter_default": [{"text": "default message"}],
        },
    }

    input_after = copy.deepcopy(input_before)
    Domain.from_dict(input_after)

    assert input_after == input_before


@pytest.mark.parametrize(
    "domain_dict", [{}, {"intents": DEFAULT_INTENTS}, {"intents": [DEFAULT_INTENTS[0]]}]
)
def test_add_default_intents(domain_dict: Dict):
    domain = Domain.from_dict(domain_dict)

    assert all(intent_name in domain.intents for intent_name in DEFAULT_INTENTS)


def test_domain_deepcopy(domain: Domain):
    new_domain = copy.deepcopy(domain)

    assert isinstance(new_domain, Domain)

    # equalities
    assert new_domain.intent_properties == domain.intent_properties
    assert new_domain.overridden_default_intents == domain.overridden_default_intents
    assert new_domain.entities == domain.entities
    assert new_domain.forms == domain.forms
    assert new_domain.form_names == domain.form_names
    assert new_domain.responses == domain.responses
    assert new_domain.action_texts == domain.action_texts
    assert new_domain.session_config == domain.session_config
    assert new_domain._custom_actions == domain._custom_actions
    assert new_domain.user_actions == domain.user_actions
    assert new_domain.action_names_or_texts == domain.action_names_or_texts
    assert new_domain.store_entities_as_slots == domain.store_entities_as_slots

    # not the same objects
    assert new_domain is not domain
    assert new_domain.intent_properties is not domain.intent_properties
    assert (
        new_domain.overridden_default_intents is not domain.overridden_default_intents
    )
    assert new_domain.entities is not domain.entities
    assert new_domain.forms is not domain.forms
    assert new_domain.form_names is not domain.form_names
    assert new_domain.slots is not domain.slots
    assert new_domain.responses is not domain.responses
    assert new_domain.action_texts is not domain.action_texts
    assert new_domain.session_config is not domain.session_config
    assert new_domain._custom_actions is not domain._custom_actions
    assert new_domain.user_actions is not domain.user_actions
    assert new_domain.action_names_or_texts is not domain.action_names_or_texts


@pytest.mark.parametrize(
    "response_key, validation",
    [("utter_chitchat/faq", True), ("utter_chitchat", False)],
)
def test_is_retrieval_intent_response(response_key, validation, domain: Domain):
    assert domain.is_retrieval_intent_response((response_key, [{}])) == validation


def test_retrieval_intent_response_seggregation():
    domain = Domain.load("data/test_domains/mixed_retrieval_intents.yml")
    assert domain.responses != domain.retrieval_intent_responses
    assert domain.responses and domain.retrieval_intent_responses
    assert list(domain.retrieval_intent_responses.keys()) == [
        "utter_chitchat/ask_weather",
        "utter_chitchat/ask_name",
    ]


def test_get_featurized_entities():
    domain = Domain.load("data/test_domains/travel_form.yml")

    user_uttered = UserUttered(
        text="Hello, I am going to London",
        intent={"name": "greet", "confidence": 1.0},
        entities=[{"entity": "GPE", "value": "London", "role": "destination"}],
    )

    featurized_entities = domain._get_featurized_entities(user_uttered)

    assert featurized_entities == set()

    user_uttered = UserUttered(
        text="I am going to London",
        intent={"inform": "greet", "confidence": 1.0},
        entities=[{"entity": "GPE", "value": "London", "role": "destination"}],
    )

    featurized_entities = domain._get_featurized_entities(user_uttered)

    assert featurized_entities == {"GPE", f"GPE{ENTITY_LABEL_SEPARATOR}destination"}


def test_featurized_entities_ordered_consistently():
    """Check that entities get ordered -- needed for consistent state representations.

    Previously, no ordering was applied to entities, but they were ordered implicitly
    due to how python sets work -- a set of all entity names was internally created,
    which was ordered by the hashes of the entity names. Now, entities are sorted alpha-
    betically. Since even sorting based on randomised hashing can produce alphabetical
    ordering once in a while, we here check with a large number of entities, pushing to
    ~0 the probability of correctly sorting the elements just by accident, without
    actually doing proper sorting.
    """
    # Create a sorted list of entity names from 'a' to 'z', and two randomly shuffled
    # copies.
    entity_names_sorted = [chr(i) for i in range(ord("a"), ord("z") + 1)]
    entity_names_shuffled1 = entity_names_sorted.copy()
    random.shuffle(entity_names_shuffled1)
    entity_names_shuffled2 = entity_names_sorted.copy()
    random.shuffle(entity_names_shuffled2)

    domain = Domain.from_dict(
        {KEY_INTENTS: ["inform"], KEY_ENTITIES: entity_names_shuffled1}
    )

    tracker = DialogueStateTracker.from_events(
        "story123",
        [
            UserUttered(
                text="hey there",
                intent={"name": "inform", "confidence": 1.0},
                entities=[
                    {"entity": e, "value": e.upper()} for e in entity_names_shuffled2
                ],
            )
        ],
    )
    state = domain.get_active_state(tracker)

    # Whatever order the entities were listed in, they should get sorted alphabetically
    # so the states' representations are consistent and entity-order-agnostic.
    assert state["user"]["entities"] == tuple(entity_names_sorted)


@pytest.mark.parametrize(
    "domain_as_dict",
    [
        # No slots
        {KEY_SLOTS: {}},
        # Valid slot mappings
        {
            KEY_SLOTS: {
                "slot_x": {
                    "type": "text",
                    "mappings": [{"type": "from_entity", "entity": "name"}],
                }
            }
        },
        {
            KEY_SLOTS: {
                "slot_x": {
                    "type": "float",
                    "mappings": [{"type": "from_intent", "value": 5}],
                }
            },
        },
        {
            KEY_SLOTS: {
                "slot_x": {
                    "type": "text",
                    "mappings": [{"type": "from_intent", "value": "some value"}],
                }
            }
        },
        {
            KEY_SLOTS: {
                "slot_x": {
                    "type": "bool",
                    "mappings": [{"type": "from_intent", "value": False}],
                }
            }
        },
        {
            KEY_SLOTS: {
                "slot_x": {
                    "type": "float",
                    "mappings": [{"type": "from_trigger_intent", "value": 5}],
                }
            },
            KEY_FORMS: {"some_form": {"required_slots": ["slot_x"]}},
        },
        {
            KEY_SLOTS: {
                "slot_x": {
                    "type": "text",
                    "mappings": [
                        {"type": "from_trigger_intent", "value": "some value"}
                    ],
                }
            },
            KEY_FORMS: {"some_form": {"required_slots": ["slot_x"]}},
        },
        {KEY_SLOTS: {"slot_x": {"type": "text", "mappings": [{"type": "from_text"}]}}},
    ],
)
def test_valid_slot_mappings(domain_as_dict: Dict[Text, Any]):
    Domain.from_dict(domain_as_dict)


@pytest.mark.parametrize(
    "domain_as_dict",
    [
        # Wrong type for forms
        {KEY_FORMS: []},
        # Wrong type for required_slots
        {KEY_FORMS: {"my_form": []}},
        {KEY_FORMS: {"my_form": 5}},
        # ignored_intent in forms, but no required_slots
        {KEY_FORMS: {"my_form": {"ignored_intents": ["greet"]}}},
    ],
)
def test_form_invalid_mappings(domain_as_dict: Dict[Text, Any]):
    with pytest.raises(InvalidDomain):
        Domain.from_dict(domain_as_dict)


def test_form_invalid_required_slots_raises():
    with pytest.raises(YamlValidationException):
        Domain.from_yaml(
            """
            version: "3.0"
            entities:
            - some_entity
            forms:
              my_form:
                required_slots:
                  some_slot:
                  - type: from_entity
                    entity: some_entity
        """
        )


@pytest.mark.parametrize(
    "domain_as_dict",
    [
        # Unknown mapping
        {KEY_SLOTS: {"my_slot": {"type": "text", "mappings": [{"type": "test"}]}}},
        # Mappings with missing keys
        {
            KEY_SLOTS: {
                "my_slot": {
                    "type": "text",
                    "mappings": [{"type": "from_entity", "intent": "greet"},],
                }
            }
        },
        {
            KEY_SLOTS: {
                "my_slot": {"type": "text", "mappings": [{"type": "from_intent"}],}
            }
        },
        {
            KEY_SLOTS: {
                "my_slot": {
                    "type": "text",
                    "mappings": [{"type": "from_intent", "value": None},],
                }
            }
        },
        {
            KEY_SLOTS: {
                "my_slot": {
                    "type": "text",
                    "mappings": [{"type": "from_trigger_intent"}],
                }
            }
        },
        {
            KEY_SLOTS: {
                "my_slot": {
                    "type": "text",
                    "mappings": [{"type": "from_trigger_intent", "value": None},],
                }
            }
        },
    ],
)
def test_slot_invalid_mappings(domain_as_dict: Dict[Text, Any]):
    with pytest.raises(InvalidDomain):
        Domain.from_dict(domain_as_dict)


@pytest.mark.parametrize(
    "domain_yaml",
    [
        # Wrong type for slots
        (
            """
        version: "3.0"
        slots:
          []
        """
        ),
        # Wrong type for slot names
        (
            """
        version: "3.0"
        slots:
          some_slot: 5
        """
        ),
        (
            """
        version: "3.0"
        slots:
          some_slot: []
        """
        ),
    ],
)
def test_invalid_slots_raises_yaml_exception(domain_yaml: Text):
    with pytest.raises(YamlValidationException):
        Domain.from_yaml(domain_yaml)


def test_slot_order_is_preserved():
    test_yaml = f"""version: '{LATEST_TRAINING_DATA_FORMAT_VERSION}'
session_config:
  session_expiration_time: 60
  carry_over_slots_to_new_session: true
slots:
  confirm:
    type: bool
    influence_conversation: false
    mappings:
    - type: custom
  previous_email:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  caller_id:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  email:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  incident_title:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  priority:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  problem_description:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  requested_slot:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  handoff_to:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
"""

    domain = Domain.from_yaml(test_yaml)
    assert domain.as_yaml(clean_before_dump=True) == test_yaml


def test_slot_order_is_preserved_when_merging():
    slot_1 = """
  b:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  a:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text"""

    test_yaml_1 = f"""
slots:{slot_1}
"""

    slot_2 = """
  d:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text
  c:
    type: text
    influence_conversation: false
    mappings:
    - type: from_text"""

    test_yaml_2 = f"""
slots:{slot_2}
"""

    test_yaml_merged = f"""version: '{LATEST_TRAINING_DATA_FORMAT_VERSION}'
session_config:
  session_expiration_time: 60
  carry_over_slots_to_new_session: true
slots:{slot_2}{slot_1}
"""

    domain_1 = Domain.from_yaml(test_yaml_1)
    domain_2 = Domain.from_yaml(test_yaml_2)
    domain_merged = domain_1.merge(domain_2)

    assert domain_merged.as_yaml(clean_before_dump=True) == test_yaml_merged


def test_responses_text_multiline_is_preserved():
    test_yaml = f"""version: '{LATEST_TRAINING_DATA_FORMAT_VERSION}'
session_config:
  session_expiration_time: 60
  carry_over_slots_to_new_session: true
responses:
  utter_confirm:
  - text: |-
      First line
      Second line
      Third line
  - text: One more response
  utter_cancel:
  - text: First line
  - text: Second line
"""

    domain = Domain.from_yaml(test_yaml)
    assert domain.as_yaml(clean_before_dump=True) == test_yaml


def test_is_valid_domain_doesnt_raise_with_valid_domain(tmpdir: Path):
    domain_path = str(tmpdir / "domain.yml")
    rasa.shared.utils.io.write_text_file(
        """
       responses:
         utter_greet:
           - text: hey there! """,
        domain_path,
    )
    assert Domain.is_domain_file(domain_path)


def test_is_valid_domain_doesnt_raise_with_invalid_domain(tmpdir: Path):
    domain_path = str(tmpdir / "domain.yml")
    rasa.shared.utils.io.write_text_file(
        """
       invalid""",
        domain_path,
    )
    assert not Domain.is_domain_file(domain_path)


def test_is_valid_domain_doesnt_raise_with_invalid_yaml(tmpdir: Path):
    potential_domain_path = str(tmpdir / "domain.yml")
    rasa.shared.utils.io.write_text_file(
        """
       script:
        - echo "Latest SDK version is ${RASA_SDK_VERSION}""",
        potential_domain_path,
    )
    assert not Domain.is_domain_file(potential_domain_path)


def test_domain_with_empty_intent_mapping():
    # domain.yml with intent (intent_name) that has a `:` character
    # and nothing after it.
    test_yaml = """intents:
    - intent_name:"""

    with pytest.raises(InvalidDomain):
        Domain.from_yaml(test_yaml).as_dict()


def test_domain_with_empty_entity_mapping():
    # domain.yml with entity (entity_name) that has a `:` character
    # and nothing after it.
    test_yaml = """entities:
    - entity_name:"""

    with pytest.raises(InvalidDomain):
        Domain.from_yaml(test_yaml).as_dict()


def test_ignored_intents_slot_mappings_invalid_domain():
    domain_as_dict = {
        KEY_FORMS: {
            "my_form": {
                IGNORED_INTENTS: "some_not_intent",
                "slot_x": [
                    {
                        "type": "from_entity",
                        "entity": "name",
                        "not_intent": "other_not_intent",
                    }
                ],
            }
        },
    }
    with pytest.raises(InvalidDomain):
        Domain.from_dict(domain_as_dict)


def test_domain_count_conditional_response_variations():
    domain = Domain.from_file(
        path="data/test_domains/conditional_response_variations.yml"
    )
    count_conditional_responses = domain.count_conditional_response_variations()
    assert count_conditional_responses == 5


def test_domain_with_no_form_slots():
    domain = Domain.from_yaml(
        """
        version: "3.0"
        forms:
         contract_form:
          required_slots: []
        """
    )
    assert domain.required_slots_for_form("contract_form") == []


def test_domain_with_empty_required_slots():
    with pytest.raises(YamlException):
        Domain.from_yaml(
            """
            version: "3.0"
            forms:
              contract_form:
            """
        )


def test_domain_invalid_yml_in_folder():
    """
    Check if invalid YAML files in a domain folder lead to the proper UserWarning
    """
    with pytest.warns(UserWarning, match="The file .* your file\\."):
        Domain.from_directory("data/test_domains/test_domain_from_directory/")


def test_domain_with_duplicates():
    """
    Check if a domain with duplicated slots, responses and intents in domain files
    removes the duplications in the domain.
    """
    domain = Domain.from_directory("data/test_domains/test_domain_with_duplicates/")
    expected_intents = [
        "affirm",
        "back",
        "bot_challenge",
        "deny",
        "goodbye",
        "greet",
        "mood_great",
        "mood_unhappy",
        "nlu_fallback",
        "out_of_scope",
        "restart",
        "session_start",
        "test",
    ]
    expected_responses = {
        "utter_greet": [{"text": "Hey! How are you?"}],
        "utter_did_that_help": [{"text": "Did that help you?"}],
        "utter_happy": [{"text": "Great, carry on!"}],
        "utter_cheer_up": [
            {
                "text": "Here is something to cheer you up:",
                "image": "https://i.imgur.com/nGF1K8f.jpg",
            }
        ],
        "utter_goodbye": [{"text": "Bye"}],
        "utter_iamabot": [{"text": "I am a bot, powered by Rasa."}],
    }
    assert domain.intents == expected_intents
    assert domain.responses == expected_responses
    assert domain.duplicates["slots"] == ["mood"]
    assert domain.duplicates["responses"] == ["utter_did_that_help", "utter_greet"]
    assert domain.duplicates["intents"] == ["greet"]


def test_domain_without_duplicates():
    """
    Check if a domain without duplicated slots, responses and intents contains
    nothing in `duplicates` field.
    """
    domain = Domain.from_directory("data/test_domains/test_domain_without_duplicates/")
    assert domain.duplicates == {}


def test_domain_duplicates_when_one_domain_file():
    """
    Check if a domain with duplicated slots, responses and intents contains
    a correct information in `duplicates` field.
    """
    domain = Domain.from_file(path="data/test_domains/default.yml")
    assert domain.duplicates is None


def test_domain_fingerprint_consistency_across_runs():
    domain_yaml = """
         version: "3.0"
         intents:
         - greet
         - goodbye
         entities:
         - name
         slots:
           name:
             type: text
             mappings:
             - type: from_entity
               entity: name
         responses:
           utter_greet:
             - text: "Hi"
         forms:
          test_form:
            required_slots:
               - name
         actions:
         - action_test
    """
    domain1 = Domain.from_yaml(domain_yaml)
    domain2 = Domain.from_yaml(domain_yaml)

    f1 = domain1.fingerprint()
    f2 = domain2.fingerprint()
    assert f1 == f2


def test_domain_fingerprint_uniqueness():
    domain = Domain.from_yaml(
        """
         version: "3.0"
         intents:
         - greet
         - goodbye
         actions:
         - action_test
         """
    )
    f1 = domain.fingerprint()

    domain_with_extra_intent = Domain.from_yaml(
        """
        version: "3.0"
        intents:
        - greet
        - goodbye
        - test
        actions:
        - action_test
        """
    )
    f2 = domain_with_extra_intent.fingerprint()
    assert f1 != f2

    domain_with_extra_action = Domain.from_yaml(
        """
        version: "3.0"
        intents:
        - greet
        - goodbye
        actions:
        - action_test
        - action_double_test
        """
    )
    f3 = domain_with_extra_action.fingerprint()
    assert f1 != f3

    domain_with_extra_responses = Domain.from_yaml(
        """
        version: "3.0"
        intents:
        - greet
        - goodbye
        responses:
          utter_greet:
           - text: "Hi!"
        actions:
        - action_test
        """
    )
    f4 = domain_with_extra_responses.fingerprint()
    assert f1 != f4


def test_domain_slots_for_entities_with_mapping_conditions_no_slot_set():
    domain = Domain.from_yaml(
        textwrap.dedent(
            """
            version: "3.0"
            entities:
            - city
            slots:
              location:
                type: text
                influence_conversation: false
                mappings:
                - type: from_entity
                  entity: city
                  conditions:
                  - active_loop: booking_form
            forms:
              booking_form:
                required_slots:
                  - location
            """
        )
    )
    events = domain.slots_for_entities([{"entity": "city", "value": "Berlin"}])
    assert len(events) == 0


def test_domain_slots_for_entities_sets_valid_slot():
    domain = Domain.from_yaml(
        textwrap.dedent(
            """
            version: "3.0"
            entities:
            - city
            slots:
              location:
                type: text
                influence_conversation: false
                mappings:
                - type: from_entity
                  entity: city
            """
        )
    )
    events = domain.slots_for_entities([{"entity": "city", "value": "Berlin"}])
    assert events == [SlotSet("location", "Berlin")]


def test_domain_slots_for_entities_sets_valid_list_slot():
    domain = Domain.from_yaml(
        textwrap.dedent(
            """
            version: "3.0"
            entities:
            - topping
            slots:
              toppings:
                type: list
                influence_conversation: false
                mappings:
                - type: from_entity
                  entity: topping
            """
        )
    )
    events = domain.slots_for_entities(
        [
            {"entity": "topping", "value": "parmesan"},
            {"entity": "topping", "value": "prosciutto"},
        ]
    )
    assert events == [SlotSet("toppings", ["parmesan", "prosciutto"])]


def test_domain_slots_for_entities_with_entity_mapping_to_multiple_slots():
    domain = Domain.from_yaml(
        """
        version: "3.0"
        entities:
        - city
        slots:
          departure_city:
            type: text
            mappings:
            - type: from_entity
              entity: city
              role: from
          arrival_city:
            type: text
            mappings:
            - type: from_entity
              entity: city
              role: to
        """
    )
    events = domain.slots_for_entities(
        [
            {"entity": "city", "value": "London", "role": "from"},
            {"entity": "city", "value": "Berlin", "role": "to"},
        ]
    )
    assert events == [
        SlotSet("departure_city", "London"),
        SlotSet("arrival_city", "Berlin"),
    ]
