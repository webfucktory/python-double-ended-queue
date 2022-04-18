# PEP0440 compatible formatted version, see:
# https://www.python.org/dev/peps/pep-0440/
#
# Generic release markers:
#   X.Y.0   # For first release after an increment in Y
#   X.Y.Z   # For bugfix releases
__version__ = '0.1.0'

from .deque import Deque
from .fifo_deque import FifoDeque
from .lifo_deque import LifoDeque
