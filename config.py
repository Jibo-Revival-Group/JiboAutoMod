###########################################
# JIBO MOD TOOL DEV VARIABLES ... WE SHOULDNT PACKAGE THESE IN UPSTREAM RELEASES GENERALLY
# BUT GOOD FOR DEBUGGING / TESTING
###########################################
LOAD_DEV_CONFIG = True


#######################################################
# Mod mode determines the approach to hack the device # 
# --------------------------------------------------- # 
# | Mode         | Approach                         | # 
# |==============|==================================| # 
# |- var         | - Changes value inside mode.json | #
# |              | to "int-developer"               | # 
# |- firewall    | - Suppresses the firewall file   | # 
# |==============|==================================| #
#######################################################

Mod_Mode = "var"

# Firewall plugin options. The normal Dev menu path opens SSH access while
# preserving mode.json; set this to True for an explicit recovery run.
FIREWALL_RESTORE = False


SKIP_SHOFEL = False

#######################################################
# Dump options                                          #
# --------------------------------------------------- # 
# | Option       | Description                       | # 
# |==============|===================================| # 
# |- SKIP_DUMP   | Skip dump entirely, use existing  | #
# |              | dump files                        | #
# |- FULL_DUMP   | Force full eMMC dump instead of   | #
# |              | optimized var-only dump           | #
# |==============|===================================| #
#######################################################

SKIP_DUMP = False
FULL_DUMP = False
