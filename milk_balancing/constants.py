"""Shared constants for the milk balancing LP problem."""

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

T = 12  # planning horizon (months)
NP = 3  # number of plants
NS = 3  # number of spot suppliers
NK = 2  # number of sales customers

# Directed transfer routes between plants: (source, destination)
ROUTES = [(0, 1), (1, 0), (1, 2), (2, 1), (0, 2), (2, 0)]
ROUTE_LBL = ["P1→P2", "P2→P1", "P2→P3", "P3→P2", "P1→P3", "P3→P1"]

# Human-readable labels
P_NAMES = ["Plant 1 (North)", "Plant 2 (South)", "Plant 3 (Central)"]
S_NAMES = ["S1 (North)", "S2 (South)", "S3 (Central)"]
FARM_NAMES = ["Farm A", "Farm B", "Farm C"]
