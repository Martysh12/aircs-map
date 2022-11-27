import json
import pygame
import math
import threading
import websocket
import rel

# PYGAME INIT

pygame.init()
pygame.font.init()

# PYGAME CONSTANTS

SIZE = WIDTH, HEIGHT = 800, 600
FPS = 60

# GLOBAL CONSTANTS

WS_URL = "ws://bnbnav.aircs.racing/ws"
PATH = "waypoints.json"
FONT = pygame.font.SysFont("Noto Sans", 12)

WAYPOINT_SIZE = 10
WAYPOINT_SIZE_MIN = 12

# GLOBALS

data = {}
players = {}
last_path = []

# CAMERA CONSTANTS

MIN_ZOOM = 0.01
MAX_ZOOM = 5
ZOOM_STEPS = 20

# CAMERA GLOBALS

moving_camera = False

camera_x = 0
camera_y = 0
camera_zoom = MIN_ZOOM

camera_zoom_step = 0

# SELECTION GLOBALS
selected_waypoint = None

# FLAGS
show_labels = True
show_players = True
show_debug_ids = False

# USEFUL CLASSES
class Node:
    """Internal node class for A* pathfinding"""

    def __init__(self, node_id):
        self.node_id = node_id

        self.parent = None

        self.g = 0 # Estimated distance from end
        self.h = 0 # Distance from start
        self.f = 0 # Cost of the node

    def __eq__(self, other):
        return self.node_id == other.node_id

    def __lt__(self, other):
        return self.f < other.f

    def __gt__(self, other):
        return self.f > other.f

    def __le__(self, other):
        return self.f <= other.f

    def __ge__(self, other):
        return self.f >= other.f

    def __repr__(self):
        return "Node(%d)" % self.node_id

# USEFUL FUNCTIONS

def load_waypoints():
    global data
    with open(PATH, "r") as f:
        data = json.load(f)

def save_waypoints():
    with open(PATH, "w") as f:
        json.dump(data, f, indent=4)

def find_waypoint_by_id(w_id):
    return tuple(filter(lambda x: x["id"] == w_id, data["waypoints"]))[0]

def find_line_by_ids(w1_id, w2_id):
    s1 = {w1_id, w2_id}

    for l in data["lines"]:
        s2 = {l["p1"], l["p2"]}

        if s1 == s2:
            return l

    return None

def apply_camera(x, y):
    return (
        ((x - camera_x) * camera_zoom) + WIDTH  / 2,
        ((y - camera_y) * camera_zoom) + HEIGHT / 2
    )

def apply_camera_zoom(r):
    return r * camera_zoom

def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))

def point_circle_collision(point_x, point_y, circle_x, circle_y, circle_r):
    return math.sqrt((point_x - circle_x) ** 2 + (point_y - circle_y) ** 2) <= circle_r

def point_rect_collision(point_x, point_y, rect_x, rect_y, rect_w, rect_h):
    return point_x >= rect_x and point_x <= rect_x + rect_w and point_y >= rect_y and point_y <= rect_y + rect_h

def line_rect_collision(line_x1, line_y1, line_x2, line_y2, rect_x, rect_y, rect_w, rect_h):
    def line_line_collision(line1_x1, line1_y1, line1_x2, line1_y2, line2_x1, line2_y1, line2_x2, line2_y2):
        u_a = ((line2_x2 - line2_x1) * (line1_y1 - line2_y1) - (line2_y2 - line2_y1) * (line1_x1 - line2_x1)) / ((line2_y2 - line2_y1) * (line1_x2 - line1_x1) - (line2_x2 - line2_x1) * (line1_y2 - line1_y1))
        u_b = ((line1_x2 - line1_x1) * (line1_y1 - line2_y1) - (line1_y2 - line1_y1) * (line1_x1 - line2_x1)) / ((line2_y2 - line2_y1) * (line1_x2 - line1_x1) - (line2_x2 - line2_x1) * (line1_y2 - line1_y1))

        return 0 <= u_a <= 1 and 0 <= u_b <= 1
    try:
        left   = line_line_collision(line_x1, line_y1, line_x2, line_y2, rect_x,          rect_y,          rect_x,          rect_y + rect_h)
        right  = line_line_collision(line_x1, line_y1, line_x2, line_y2, rect_x + rect_w, rect_y,          rect_x + rect_w, rect_y + rect_h)
        top    = line_line_collision(line_x1, line_y1, line_x2, line_y2, rect_x,          rect_y,          rect_x + rect_w, rect_y)
        bottom = line_line_collision(line_x1, line_y1, line_x2, line_y2, rect_x,          rect_y + rect_h, rect_x + rect_w, rect_y + rect_h)
    except ZeroDivisionError:
        return False

    # That was really painful to write

    return left or right or top or bottom

def get_waypoint_under_point(point_x, point_y):
    for w in data["waypoints"]:
        waypoint_camera_pos = apply_camera(w["pos"][0], w["pos"][1])
        waypoint_camera_scale_pixels = clamp(apply_camera_zoom(WAYPOINT_SIZE), WAYPOINT_SIZE_MIN, float("inf"))
        if point_rect_collision(point_x, point_y, waypoint_camera_pos[0] - waypoint_camera_scale_pixels / 2, waypoint_camera_pos[1] - waypoint_camera_scale_pixels / 2, waypoint_camera_scale_pixels, waypoint_camera_scale_pixels):
            return w

def find_path_a_star(start_waypoint_id, end_waypoint_id):
    # Create start and end nodes
    start_node = Node(start_waypoint_id)
    end_node = Node(end_waypoint_id)
    
    # Get end waypoint. We'll need it later!
    end_waypoint = find_waypoint_by_id(end_waypoint_id)
    
    open_list = []
    closed_list = []

    # Add the start node to the open list
    open_list.append(start_node)

    # Loop until no nodes left
    while len(open_list) > 0:
        # Get node with lowest cost in open list
        current_node = min(open_list)
        current_index = open_list.index(current_node)
        
        # Pop current node off the open list, and add it to the closed list.
        open_list.pop(current_index)
        closed_list.append(current_node)

        # Have we found the goal yet?
        if current_node == end_node:
            # We have! Let's backtrack.
            path = []

            current = current_node

            while current is not None:
                path.append(current.node_id)
                current = current.parent
            
            #print(open_list, closed_list)

            return path[::-1] # We backtracked. Reverse the path to get the forward-track.

        # Find the children
        children = []
        
        for l in data["lines"]:
            # Sets are swag.
            point_set = {l["p1"], l["p2"]}

            if current_node.node_id not in point_set:
                continue
            
            # Aquire the other node ID from the set.
            point_set.remove(current_node.node_id)
            
            try:
                new_node_id = point_set.pop()
            except KeyError:
                print(l, find_waypoint_by_id(l["p1"]), find_waypoint_by_id(l["p2"]))
                return None

            new_node = Node(new_node_id) # Create the node!

            children.append(new_node) # Append the child to the... children.

        # Get the current waypoint (we'll need it later!)
        current_waypoint = find_waypoint_by_id(current_node.node_id)

        # Process the children
        for child in children:
            if child in closed_list: # Have we processed this node already?
                continue # We have. NEXT!

            # Get the distance between this node and the child
            child_waypoint = find_waypoint_by_id(child.node_id)
            
            # Store the distance between the current node and the child node in G
            child.g = current_node.g + math.dist(current_waypoint["pos"], child_waypoint["pos"])
            
            # Multiply the distance by 

            # Store the estimated distance from the child node and the end node in H
            child.h = math.dist(child_waypoint["pos"], end_waypoint["pos"])
            # Store the total cost of the child node in F
            child.f = child.g + child.h
            # And of course, set the parent as the current node
            child.parent = current_node

            do_continue = False
            for open_node in open_list:
                if child == open_node and child.g > open_node.g:
                    do_continue = True
            
            if do_continue:
                continue

            open_list.append(child)

# WEBSOCKET

def websocket_loop_thread(quit_event):
    #websocket.enableTrace(True)
    ws = websocket.WebSocket()
    ws.connect(WS_URL)

    while not quit_event.is_set():
        message = ws.recv()

        message = json.loads(message)

        global players
        if message["type"] == "playerMove":
            players[message["id"]] = {"pos": (message["x"], message["z"])}
        if message["type"] == "playerGone":
            del players[message["id"]]

    ws.close()

# LOAD WAYPOINTS

load_waypoints()

#print(waypoints)

# PYGAME STUFF

screen = pygame.display.set_mode(SIZE)
pygame.display.set_caption("Google Maps")

clock = pygame.time.Clock()

# LOGOS

logo_aircs   = pygame.image.load("logos/aircs.png")
logo_sqtr    = pygame.image.load("logos/sqtr.png")
logo_clyrail = pygame.image.load("logos/clyrail.png")

# THREADING

quit_event = threading.Event()

t = threading.Thread(target=websocket_loop_thread, daemon=True, args=(quit_event,))
t.start()

# MAIN LOOP

running = True
while running:
    clock.tick(FPS)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
        # MOVING
        elif event.type == pygame.MOUSEBUTTONDOWN:
            #print(event.button)
            if event.button == 1: # Left button
                w = get_waypoint_under_point(*event.pos)

                if w is not None:
                    if w["id"] == selected_waypoint:
                        selected_waypoint = None
                    else:
                        selected_waypoint = w["id"]

            if event.button == 2: # Middle button
                moving_camera = True
            
            if event.button == 3: # Right button
                if selected_waypoint is not None:
                    w = get_waypoint_under_point(*event.pos)
                    
                    if w is not None:
                        if w["id"] != selected_waypoint:
                            # Verify that the line we're about to delete exists
                            valid = True
                            
                            delete_index = None
                            for il, l in enumerate(data["lines"]):
                                # These are not dictionaries, these are sets.
                                if {l["p1"], l["p2"]} == {w["id"], selected_waypoint}:
                                    delete_index = il
                                    break
                            
                            if delete_index is not None:
                                del data["lines"][delete_index]

            if event.button == 7 or event.button == 6: # Side/front button or Side/back button
                if selected_waypoint is not None:
                    w = get_waypoint_under_point(*event.pos)

                    if w is not None:
                        if w["id"] != selected_waypoint:
                            # Verify that the line we're about to create is new
                            valid = True

                            for l in data["lines"]:
                                # These are not dictionaries, these are sets.
                                if {l["p1"], l["p2"]} == {w["id"], selected_waypoint}:
                                    valid = False

                            if valid:
                                data["lines"].append({"p1": selected_waypoint, "p2": w["id"], "type": 0 if event.button == 7 else 1})
                                selected_waypoint = None
        

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2: # Middle button
                moving_camera = False

        elif event.type == pygame.MOUSEMOTION:
            if moving_camera:
                camera_x -= event.rel[0] / camera_zoom
                camera_y -= event.rel[1] / camera_zoom

        # ZOOMING
        elif event.type == pygame.MOUSEWHEEL:
            camera_zoom_step += event.y

            log_min_zoom = math.log(MIN_ZOOM)
            log_max_zoom = math.log(MAX_ZOOM)
            log_zoom = log_min_zoom + (log_max_zoom - log_min_zoom) * camera_zoom_step / (ZOOM_STEPS - 1)
            camera_zoom = math.exp(log_zoom)

        # KEYS
        elif event.type == pygame.KEYDOWN:
            # TOGGLE LABELS
            if event.key == pygame.K_l:
                show_labels = not show_labels

            # TOGGLE PLAYERS
            if event.key == pygame.K_p:
                show_players = not show_players

            # TOGGLE DEBUG IDS
            if event.key == pygame.K_d:
                show_debug_ids = not show_debug_ids

            # RELOAD WAYPOINTS
            if event.key == pygame.K_r:
                load_waypoints()
                last_path = [] # Reset path because the IDs are refreshed every time

            # SAVE DATA
            if event.key == pygame.K_s:
                save_waypoints()

            # FIND PATH
            if event.key == pygame.K_f:
                if selected_waypoint is not None:
                    w = get_waypoint_under_point(*pygame.mouse.get_pos())

                    if w is not None:
                        last_path = find_path_a_star(selected_waypoint, w["id"])

                        if last_path is None:
                            last_path = []

    # UPDATE STUFF HERE

    # DRAW STUFF HERE
    
    screen.fill((36, 34, 31))
    
    # RENDER LINES
    for l in data["lines"]:
        first_waypoint = find_waypoint_by_id(l["p1"])
        second_waypoint = find_waypoint_by_id(l["p2"])

        first_waypoint_camera_pos = apply_camera(first_waypoint["pos"][0], first_waypoint["pos"][1])
        second_waypoint_camera_pos = apply_camera(second_waypoint["pos"][0], second_waypoint["pos"][1])

        if point_rect_collision(*first_waypoint_camera_pos, 0, 0, WIDTH, HEIGHT) \
            or point_rect_collision(*second_waypoint_camera_pos, 0, 0, WIDTH, HEIGHT) \
            or line_rect_collision(*first_waypoint_camera_pos, *second_waypoint_camera_pos, 0, 0, WIDTH, HEIGHT):
            pygame.draw.line(screen, (255, 255, 255) if l["type"] == 0 else (128, 128, 128), first_waypoint_camera_pos, second_waypoint_camera_pos, width=int(clamp(apply_camera_zoom(5), 2, float("inf"))))

    # RENDER WAYPOINTS

    for w in data["waypoints"]:
        waypoint_camera_pos = apply_camera(w["pos"][0], w["pos"][1])
        waypoint_camera_scale_pixels = clamp(apply_camera_zoom(WAYPOINT_SIZE), WAYPOINT_SIZE_MIN, float("inf"))

        if point_rect_collision(*waypoint_camera_pos, -waypoint_camera_scale_pixels, -waypoint_camera_scale_pixels, WIDTH + waypoint_camera_scale_pixels * 2, HEIGHT + waypoint_camera_scale_pixels * 2):
            #color = (212, 64, 44)  if w["type"] == "AirCS"   else (
            #        (55, 66, 219)  if w["type"] == "SQTR"    else (
            #        (73, 216, 235) if w["type"] == "SkyRail" else (
            #        (237, 227, 26) if w["type"] == "ClyRail" else (255, 255, 255))))
            
            logo_to_use = logo_aircs   if w["type"] == "AirCS"   else (
                          logo_sqtr    if w["type"] == "SQTR"    else (
                          logo_clyrail if w["type"] == "ClyRail" else None))

            if logo_to_use is not None:
                screen.blit(
                    pygame.transform.scale(logo_to_use, (waypoint_camera_scale_pixels,) * 2),
                    (
                        waypoint_camera_pos[0] - waypoint_camera_scale_pixels // 2,
                        waypoint_camera_pos[1] - waypoint_camera_scale_pixels // 2
                    )
                )
            else:
                pygame.draw.circle(
                    screen,
                    (73, 216, 235),#color,
                    waypoint_camera_pos,
                    waypoint_camera_scale_pixels // 2,
                    int(clamp(apply_camera_zoom(5), 2, float("inf")))
                )

            if selected_waypoint == w["id"]:
                pygame.draw.circle(
                    screen,
                    (255, 255, 255),
                    waypoint_camera_pos,
                    clamp(apply_camera_zoom(5.1), 5, float("inf"))
                )

            if show_labels:
                text_surface = FONT.render(f" {w['name']} {tuple(w['pos'])}{' ' + str(w['id']) if show_debug_ids else ''} ", True, (255, 255, 255), (0, 0, 0)).convert_alpha()
                text_surface.set_alpha(192)
                screen.blit(text_surface, (waypoint_camera_pos[0] + 6, waypoint_camera_pos[1] + 6))
        
        # RENDER PLAYERS
        if show_players:
            try:
                for name, p in players.items():
                    player_camera_pos = apply_camera(p["pos"][0], p["pos"][1])
                    player_camera_radius = clamp(apply_camera_zoom(1), 5, float("inf")) 

                    if point_rect_collision(*player_camera_pos, -player_camera_radius, -player_camera_radius, WIDTH + player_camera_radius * 2, HEIGHT + player_camera_radius * 2):
                        pygame.draw.circle(
                            screen,
                            (60, 237, 47),
                            player_camera_pos,
                            player_camera_radius
                        )

                        text_surface = FONT.render(f" {name} {tuple(map(round, p['pos']))} ", True, (255, 255, 255), (36, 41, 38)).convert_alpha()
                        text_surface.set_alpha(192)
                        screen.blit(text_surface, apply_camera(p["pos"][0], p["pos"][1]))
            except RuntimeError: # Sometimes players get deleted in the middle of rendering.
                pass

    # RENDER ORIGIN
    pygame.draw.circle(
        screen,
        (0, 255, 255),
        apply_camera(0, 0),
        clamp(apply_camera_zoom(1), 5, float("inf"))
    )

    text_surface = FONT.render(f" (0, 0) ", True, (255, 255, 255), (0, 0, 0)).convert_alpha()
    text_surface.set_alpha(192)
    screen.blit(text_surface, apply_camera(0, 0))

    # RENDER SELECTED TEXT
    try:
        w = find_waypoint_by_id(selected_waypoint)

        text_surface = FONT.render(f" Selected: {w['type']} - {w['name']} {tuple(w['pos'])} ", True, (255, 255, 255), (0, 0, 0))
        screen.blit(text_surface, (0, 0))
    except IndexError:
        pass

    # RENDER PATH
    path_positions = [apply_camera(*find_waypoint_by_id(i)["pos"]) for i in last_path]

    if len(path_positions) >= 2:
        pygame.draw.lines(screen, (0, 255, 0), False, path_positions, width=int(clamp(apply_camera_zoom(3), 3, float("inf"))))

    pygame.display.flip()

quit_event.set()

pygame.quit()

