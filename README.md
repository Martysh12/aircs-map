# aircs-map
Map of metro stations in b&amp;BMC.

## Usage
1. First, walk around b&BMC and gather hundreds of waypoints (using Xaero's Minimap) corresponding to each station. Name them like this: `<Station type, may be "SQTR", "ClyRail" or "SkyRail". "AirCS" will be ignored because Victor has a reliable source> - <Station name. May be anything>`
2. Then run the script called `pull_data.py`. It will try to pull waypoint data from available sources. Edit the path of the waypoint database at the start of the script if necessary. The script will complain if you're missing a waypoint.
3. Great! You're ready to run `display.py`. `display.py` is the actual map script, and it will allow you find a shortest path between 1 point to another.

## `lines.json` Documentation
 - `walkable_quadruplet`
   - You can walk between station `p1`, `p2`, `p3` and `p4` freely. Will create 6 walkable lines between those stations.
 - `walkable_triplet`
   - You can walk between station `p1`, `p2`, and `p3`. Will create 3 walkable lines between those stations.
 - `normal`
   - Will create a single normal line between `p1` and `p2`.
 - `walkable`
   - Will create a single walkable line between `p1` and `p2`.
 - `polygonal`
   - Very useful. Will create a line between station `n` and `n + 1` for each waypoint in `waypoints`.

## TODO
 - `lines.json` is unfinished. Complete all lines for SQTR stations, and add some lines for SkyRail stations.
