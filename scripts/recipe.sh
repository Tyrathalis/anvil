# The search recipe of record — ONE definition, sourced by the chain scripts
# (`. "$REPO/scripts/recipe.sh"`) the way data/pool/CURRENT pins the pool.
# Edit here only; a running chain has already read its copy (bash sources at
# the `.` line), so a change lands on the NEXT launch. The quickstart's §7a
# flag table explains every flag; ADR-0113 / ADR-0115 are the pins.
#
#   RECIPE   the serve-time search recipe (recipe + alloc arms of the shakedown; the settings pass)
#   SHALLOW  one-roll search, no surfaces (the shakedown's shallow arm)
#   DEEP     RECIPE + the priced deep round (the shakedown's deep arm; ×2.83 box time per game)
RECIPE="-search -searchrate 1 -searchrolls 2 -searchsurf 2 -searchsurfcap 8 -searchact 0.10 -searchtemp 0.025 -searchactkinds entity_one,entity_set,mode"
SHALLOW="-search -searchrate 1 -searchrolls 1 -searchact 0.10 -searchtemp 0.025"
DEEP="$RECIPE -searchdeep 3 -searchdeepleaf h2 -searchdeeprolls 4 -searchdeeplo 0.02 -searchdeepfloor 0.1 -searchclock 3600"
