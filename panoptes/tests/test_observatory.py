import pytest

import astropy.units as u

from ..observatory import Observatory
from ..utils.config import load_config

config = load_config()

obs = None


def test_no_config():
    """ Creates a blank Observatory """
    with pytest.raises(AssertionError):
        obs = Observatory()


def test_default_config():
    """ Creates a default Observatory """
    obs = Observatory(config=config)

    assert obs.location is not None
    assert obs.elevation == config['site']['elevation'] * u.meter
    assert obs.horizon == config['site']['horizon'] * u.degree