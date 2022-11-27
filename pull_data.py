import csv
import json
import os
import time
import requests

AIRCS_URL = "https://map.aircs.racing/data/stations.json"
LOCAL_LINE_STORAGE_PATH = "lines.json"
PATH = "/home/martysh12/.minecraft/XaeroWaypoints/Multiplayer_mc.aircs.racing/dim%0/mw$default_1.txt"
SAVE_PATH = "waypoints.json"

#if os.path.isfile(SAVE_PATH):
#    print("Are you sure?")
#    
#    try:
#        time.sleep(1)
#    except KeyboardInterrupt:
#        pass
#
#    while True:
#        i = input("([y]es/[n]o): ")
#
#        if i == "y":
#            break
#        if i == "n":
#            exit(0)

data = {
    "waypoints": [],
    "lines": []
}

# Pull from local waypoints
with open(PATH, "r") as f:
    reader = csv.reader(filter(lambda row: not row.startswith("#"), f), delimiter=":")

    for row in reader:
        if row[0] == "waypoint":
            type_, name = row[1].split(" - ")
            
            if type_ != "AirCS":
                waypoint = {
                    "id": hash(row[1]),
                    "type": type_,
                    "name": name,
                    "pos": [
                        int(row[3]),
                        int(row[5])
                    ]
                }


                data["waypoints"].append(waypoint)

# Pull from online source
r = requests.get(AIRCS_URL)
aircs_data = json.loads(r.content)["stations"]

for station_id, station in aircs_data.items():
    # Skip bad stations
    if station["name"] is None or station["cx"] is None or station["cz"] is None or len(station["platforms"]) == 0:
        continue

    station_hash = hash(f"AirCS - {station['name']} ({station_id})")
    
    waypoint = {
        "id": station_hash,
        "type": "AirCS",
        "_aircsId": station_id,
        "name": station["name"],
        "pos": [
            station["cx"],
            station["cz"]
        ]
    }

    data["waypoints"].append(waypoint)

def aircs_id_to_id(aircs_id):
    for w in data["waypoints"]:
        try:
            if w["_aircsId"] == aircs_id:
                return w["id"]
        except KeyError:
            pass

for station_id, station in aircs_data.items():
    if station["name"] is None or station["cx"] is None or station["cz"] is None or len(station["platforms"]) == 0:
        continue

    p1_id = aircs_id_to_id(station_id)

    for platform_num, platform in station["platforms"].items():
        p2_id = aircs_id_to_id(platform["station"])
        
        if p2_id is None:
            continue

        if {p1_id, p2_id} in map(lambda x: {x["p1"], x["p2"]}, data["lines"]):
            continue

        if p1_id == p2_id: # VICTOR WHY??????? WHY????????
            continue
        
        data["lines"].append({"p1": p1_id, "p2": p2_id, "type": 0})

# Pull from local storage

def find_id_by_identifier(identifier):
    for w in data["waypoints"]:
        if w["type"] + " - " + w["name"] == identifier:
            return w["id"]

    print("Couldn't find identifier:", identifier)

    return None

with open(LOCAL_LINE_STORAGE_PATH, "r") as f:
    local_line_data = json.load(f)

for l in local_line_data:
    if l["type"] == "walkable_quadruplet":
        p1_id = find_id_by_identifier(l["p1"])
        p2_id = find_id_by_identifier(l["p2"])
        p3_id = find_id_by_identifier(l["p3"])
        p4_id = find_id_by_identifier(l["p4"])

        data["lines"].append({"p1": p1_id, "p2": p2_id, "type": 1})
        data["lines"].append({"p1": p2_id, "p2": p3_id, "type": 1})
        data["lines"].append({"p1": p3_id, "p2": p1_id, "type": 1})
        data["lines"].append({"p1": p3_id, "p2": p4_id, "type": 1})
        data["lines"].append({"p1": p4_id, "p2": p1_id, "type": 1})
        data["lines"].append({"p1": p4_id, "p2": p2_id, "type": 1})
    
    if l["type"] == "walkable_triplet":
        p1_id = find_id_by_identifier(l["p1"])
        p2_id = find_id_by_identifier(l["p2"])
        p3_id = find_id_by_identifier(l["p3"])

        data["lines"].append({"p1": p1_id, "p2": p2_id, "type": 1})
        data["lines"].append({"p1": p2_id, "p2": p3_id, "type": 1})
        data["lines"].append({"p1": p3_id, "p2": p1_id, "type": 1})

    if l["type"] == "normal":
        p1_id = find_id_by_identifier(l["p1"])
        p2_id = find_id_by_identifier(l["p2"])

        data["lines"].append({"p1": p1_id, "p2": p2_id, "type": 0})
    
    if l["type"] == "walkable":
        p1_id = find_id_by_identifier(l["p1"])
        p2_id = find_id_by_identifier(l["p2"])

        data["lines"].append({"p1": p1_id, "p2": p2_id, "type": 1})

    if l["type"] == "polygonal":
        ids = [find_id_by_identifier(i) for i in l["waypoints"]]

        for i, v in enumerate(ids[1:]):
            data["lines"].append({"p1": ids[i], "p2": ids[i + 1], "type": 0})

# Ensure that there are no duplicate lines
data["lines"] = [i for n, i in enumerate(data["lines"]) if i not in data["lines"][:n]]

with open(SAVE_PATH, "w") as f:
    json.dump(data, f, indent=4)

