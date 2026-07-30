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


SKIP_SHOFEL = True 
