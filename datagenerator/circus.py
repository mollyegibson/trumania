import pandas as pd
from datagenerator.util_functions import merge_dicts
import logging


def df_concat(d1, d2):
        df = pd.concat([d1, d2])
        df.reset_index(drop=True, inplace=True)
        return df


class Circus(object):
    """
    A Circus is just a container of a lot of objects that are required to make the simulation
    It is also the object that will execute the actions required for 1 iteration

    The different objects contained in the Circus are:
    - Actors, which do actions during the simumation
    - Items, that contain descriptive data
    - a Clock object, to manage overall time
    - Actions, a list of actions to perform on the actors
    - Incrementors, similarly to a list of actions, it's storing which generators need to be incremented at each step

    """

    def __init__(self, clock):
        """Create a new Circus object

        :type clock: Clock object
        :param clock:
        :rtype: Circus
        :return: a new Circus object, with the clock, is created
        """
        self.__items = {}
        self.clock = clock
        self.__actions = []

    def add_item(self, name, item):
        """Add an Item object to the list of items

        :type name: str
        :param name: the name to reference the Item
        :type item: Item object
        :param item: the Item object to add
        :return: None
        """
        if self.__items.has_key(name):
            raise Exception("Already having items named %s" % name)
        self.__items[name] = item

    def add_action(self, action):
        """Add an action to perform

        :type action: Action
        :param action: the action to execute
        :type supp_fields: dict
        :param supp_fields: dictionary of additional fields to complete for the action logs
        Currently, the dictionary can have 2 entries:
        - "timestamp": {True, False} if a timestamp needs to be added
        - "join": [list of tuples with ("field to join on",
                                        object to join on (Actor or Item),
                                        "object field to join on",
                                        "field name in output table")]
        :return:
        """
        self.__actions.append(action)

    def add_actions(self, *actions):
        for action in actions:
            self.add_action(action)

    def get_action(self, action_name):
        return filter(lambda a: a.name == action_name, self.__actions)[0]

    def get_actor_of(self, action_name):
        return self.get_action(action_name).triggering_actor

    def one_step(self, round_number):
        """
        Performs one round of actions

        :return:
        """

        logging.info("step : {}".format(round_number))

        # puts the logs of all actions into one grand dictionary.
        logs = merge_dicts((action.execute() for action in self.__actions),
                           df_concat)

        self.clock.increment()

        return logs

    def run(self, n_iterations):
        """
        Executes all actions for as many iteration as specified.

        :param n_iterations:
        :return: a list of as many dataframes as there are actions configured in
        this circus, each gathering all rows produces throughout all iterations
        """

        logging.info("starting circus")
        all_actions_logs = (self.one_step(r) for r in range(n_iterations))

        # merging logs from all actions
        return merge_dicts(all_actions_logs, df_concat)