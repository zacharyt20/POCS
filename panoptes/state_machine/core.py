import os
import yaml
import transitions

from ..utils.logger import has_logger
from ..utils.database import PanMongo
from ..utils import error, listify


@has_logger
class PanStateMachine(transitions.Machine):

    """ A finite state machine for PANOPTES.

    The state machine guides the overall action of the unit. The state machine works in the following
    way with PANOPTES::

            * The machine consists of `states` and `transitions`.
    """

    def __init__(self, *args, **kwargs):
        assert 'states' in kwargs, self.logger.warning('states keyword required.')
        assert 'transitions' in kwargs, self.logger.warning('transitions keyword required.')

        # Set up connection to database
        if not self.db:
            self.db = PanMongo()

        try:
            self.state_information = self.db.state_information
        except AttributeError as err:
            raise error.MongoCollectionNotFound(
                msg="Can't connect to mongo instance for states information table. {}".format(err))

        # For tracking the state information
        self._state_stats = dict()

        self._initial = kwargs.get('initial', 'sleeping')

        # Setup Transitions
        self._transitions = kwargs['transitions']
        self.transitions = [self._load_transition(transition) for transition in self._transitions]

        # Setup States
        self.states = kwargs['states']

        super().__init__(
            states=self.states,
            transitions=self.transitions,
            initial=self._initial,
            send_event=True,
            before_state_change='before_state',
            after_state_change='after_state'
        )

        self.logger.debug("State machine created")

##################################################################################################
# Properties
##################################################################################################


##################################################################################################
# Methods
##################################################################################################

##################################################################################################
# Callback Methods
##################################################################################################

    def before_state(self, event_data):
        """ Called before each state.

        Starts collecting stats on this particular state, which are saved during
        the call to `after_state`.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
         """
        self.logger.debug("Before going {} from {}".format(event_data.state.name, event_data.event.name))

        # self._state_stats = dict()
        # self._state_stats['state'] = event_data.state.name
        # self._state_stats['from'] = event_data.event.name.replace('to_', '')
        # self._state_stats['start_time'] = datetime.datetime.utcnow()

    def after_state(self, event_data):
        """ Called after each state.

        Updates the mongodb collection for state stats.

        Args:
            event_data(transitions.EventData):  Contains informaton about the event
        """
        self.logger.debug("After going {} from {}".format(event_data.event.name, event_data.state.name))

        # self._state_stats['stop_time'] = datetime.datetime.utcnow()
        # self.state_information.insert(self._state_stats)


##################################################################################################
# Class Methods
##################################################################################################

    @classmethod
    def load_state_table(cls, state_table_name='simple_state_table'):
        """ Loads the state table

        Args:
            state_table_name(str):  Name of state table. Corresponds to file name in
                `$POCS/resources/state_table/` directory. Default 'simple_state_table'.

        Returns:
            dict:                   Dictonary with `states` and `transitions` keys.
        """

        state_table_file = "{}/resources/state_table/{}.yaml".format(
            os.getenv('POCS', default='/var/panoptes/POCS'), state_table_name)

        state_table = {'states': [], 'transitions': []}

        try:
            with open(state_table_file, 'r') as f:
                state_table = yaml.load(f.read())
        except OSError as err:
            raise error.InvalidConfig(
                'Problem loading state table yaml file: {} {}'.format(err, state_table_file))
        except:
            raise error.InvalidConfig(
                'Problem loading state table yaml file: {}'.format(state_table_file))

        return state_table

##################################################################################################
# Private Methods
##################################################################################################

    def _load_transition(self, transition):
        self.logger.debug("Loading transition: {}".format(transition))

        # Make sure the transition has the weather_is_safe condition on it
        conditions = listify(transition.get('conditions', []))

        conditions.append('check_safety')
        transition['conditions'] = conditions

        self.logger.debug("Returning transition: {}".format(transition))
        return transition
