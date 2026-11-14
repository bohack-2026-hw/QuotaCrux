# Standard-library prelude from EffiBench-X effibench/utils.py at 21b6668a.
# Modified: omit sortedcontainers to match the standard-library sandbox.
# Upstream: https://github.com/EffiBench/EffiBench-X (Apache-2.0); see THIRD_PARTY_NOTICES.md.
import re
from re import match, search, sub, split, findall, finditer
import sys
from sys import maxsize, stdin
import json
from json import loads
import math
from math import floor, ceil, factorial, sqrt, isqrt, inf, log2, log10, sin, cos, tan, pi, e, comb, perm, gcd, lcm
import copy
import pickle
import heapq
from heapq import heappush, heappop, heapify, heappushpop, nlargest, nsmallest
import bisect
from bisect import bisect_left, bisect_right
import string
from string import ascii_letters, ascii_lowercase, ascii_uppercase, digits, whitespace, punctuation, hexdigits
import random
import operator
import itertools
from itertools import combinations, permutations, product, groupby, chain, accumulate, zip_longest
import functools
from functools import lru_cache, cache, reduce
import collections
from collections import OrderedDict, defaultdict, Counter, deque
from typing import Set, Dict, List, Optional, Tuple
