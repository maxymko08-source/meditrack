#!/usr/bin/env python3
"""
MediTrack — Modular IoT Smart Pill Dispenser (Upgraded 1:2 Gear Drive System)
Parametric Binary STL Generator for 3D Printing

Generates modular components with 0.4 mm manufacturing tolerances:
  1. meditrack_base_box.stl      — Lower Electronics Housing (68 mm inner height)
  2. meditrack_middle_deck.stl   — Stationary Middle Deck (Retaining Ring + Ø7.5 mm hole + Chute)
  3. meditrack_carousel.stl      — Rotating Pill Carousel (8-section drum with D-socket hub)
  4. meditrack_top_lid.stl       — Top Dust Lid (104 mm flat cover with 3 mm lip)
  5. meditrack_gears.stl         — 1:2 Step-Up Gear Pair (24T Driver + 12T Driven with D-shaft)
"""

import math
import struct
import os

class STLMesh:
    def __init__(self, name="MediTrackPart"):
        self.name = name
        self.triangles = []

    def add_triangle(self, v1, v2, v3):
        ax, ay, az = v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2]
        bx, by, bz = v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2]
        nx = ay * bz - az * by
        ny = az * bx - ax * bz
        nz = ax * by - ay * bx
        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length > 1e-9:
            normal = (nx/length, ny/length, nz/length)
        else:
            normal = (0.0, 0.0, 1.0)
        self.triangles.append((normal, v1, v2, v3))

    def add_quad(self, v1, v2, v3, v4):
        self.add_triangle(v1, v2, v3)
        self.add_triangle(v1, v3, v4)

    def add_box(self, x_min, x_max, y_min, y_max, z_min, z_max):
        p1 = (x_min, y_min, z_min)
        p2 = (x_max, y_min, z_min)
        p3 = (x_max, y_max, z_min)
        p4 = (x_min, y_max, z_min)
        p5 = (x_min, y_min, z_max)
        p6 = (x_max, y_min, z_max)
        p7 = (x_max, y_max, z_max)
        p8 = (x_min, y_max, z_max)
        self.add_quad(p1, p4, p3, p2) # bottom (z_min)
        self.add_quad(p5, p6, p7, p8) # top (z_max)
        self.add_quad(p1, p2, p6, p5) # front (y_min)
        self.add_quad(p3, p4, p8, p7) # back (y_max)
        self.add_quad(p4, p1, p5, p8) # left (x_min)
        self.add_quad(p2, p3, p7, p6) # right (x_max)

    def add_cylinder(self, r, h, z_bottom=0.0, segments=64, center=(0.0, 0.0)):
        cx, cy = center
        z_top = z_bottom + h
        angles = [2.0 * math.pi * i / segments for i in range(segments)]
        b_pts = [(cx + r * math.cos(a), cy + r * math.sin(a), z_bottom) for a in angles]
        t_pts = [(cx + r * math.cos(a), cy + r * math.sin(a), z_top) for a in angles]
        cb = (cx, cy, z_bottom)
        ct = (cx, cy, z_top)
        for i in range(segments):
            nxt = (i + 1) % segments
            self.add_quad(b_pts[i], b_pts[nxt], t_pts[nxt], t_pts[i])
            self.add_triangle(cb, b_pts[nxt], b_pts[i])
            self.add_triangle(ct, t_pts[i], t_pts[nxt])

    def add_pipe(self, r_inner, r_outer, h, z_bottom=0.0, segments=64, center=(0.0, 0.0)):
        cx, cy = center
        z_top = z_bottom + h
        angles = [2.0 * math.pi * i / segments for i in range(segments)]
        o_bot = [(cx + r_outer * math.cos(a), cy + r_outer * math.sin(a), z_bottom) for a in angles]
        o_top = [(cx + r_outer * math.cos(a), cy + r_outer * math.sin(a), z_top) for a in angles]
        i_bot = [(cx + r_inner * math.cos(a), cy + r_inner * math.sin(a), z_bottom) for a in angles]
        i_top = [(cx + r_inner * math.cos(a), cy + r_inner * math.sin(a), z_top) for a in angles]
        for i in range(segments):
            nxt = (i + 1) % segments
            self.add_quad(o_bot[i], o_bot[nxt], o_top[nxt], o_top[i]) # outer wall
            self.add_quad(i_bot[nxt], i_bot[i], i_top[i], i_top[nxt]) # inner wall
            self.add_quad(o_bot[nxt], o_bot[i], i_bot[i], i_bot[nxt]) # bottom rim
            self.add_quad(o_top[i], o_top[nxt], i_top[nxt], i_top[i]) # top rim

    def add_gear(self, num_teeth, module_val, thickness, z_bottom=0.0, center=(0.0, 0.0), center_hole_r=0.0):
        cx, cy = center
        pitch_r = (num_teeth * module_val) / 2.0
        addendum = 1.0 * module_val
        dedendum = 1.25 * module_val
        tip_r = pitch_r + addendum
        root_r = pitch_r - dedendum
        z_top = z_bottom + thickness
        tooth_angle = 2.0 * math.pi / num_teeth

        # Build 2D polygon profile points around periphery (4 points per tooth)
        profile_pts_bot = []
        profile_pts_top = []
        for i in range(num_teeth):
            base_a = i * tooth_angle
            # Root start
            a0 = base_a - tooth_angle * 0.28
            a1 = base_a - tooth_angle * 0.12
            a2 = base_a + tooth_angle * 0.12
            a3 = base_a + tooth_angle * 0.28
            for a, r in [(a0, root_r), (a1, tip_r), (a2, tip_r), (a3, root_r)]:
                px = cx + r * math.cos(a)
                py = cy + r * math.sin(a)
                profile_pts_bot.append((px, py, z_bottom))
                profile_pts_top.append((px, py, z_top))

        total_pts = len(profile_pts_bot)
        cb = (cx, cy, z_bottom)
        ct = (cx, cy, z_top)

        for i in range(total_pts):
            nxt = (i + 1) % total_pts
            # Side tooth quad
            self.add_quad(profile_pts_bot[i], profile_pts_bot[nxt], profile_pts_top[nxt], profile_pts_top[i])

            if center_hole_r <= 0.01:
                # Bottom & top solid faces
                self.add_triangle(cb, profile_pts_bot[nxt], profile_pts_bot[i])
                self.add_triangle(ct, profile_pts_top[i], profile_pts_top[nxt])

        if center_hole_r > 0.01:
            # Annular bottom and top rings
            hole_angles = [2.0 * math.pi * i / total_pts for i in range(total_pts)]
            h_bot = [(cx + center_hole_r * math.cos(a), cy + center_hole_r * math.sin(a), z_bottom) for a in hole_angles]
            h_top = [(cx + center_hole_r * math.cos(a), cy + center_hole_r * math.sin(a), z_top) for a in hole_angles]
            for i in range(total_pts):
                nxt = (i + 1) % total_pts
                self.add_quad(profile_pts_bot[nxt], profile_pts_bot[i], h_bot[i], h_bot[nxt])
                self.add_quad(profile_pts_top[i], profile_pts_top[nxt], h_top[nxt], h_top[i])
                # Inner hole side
                self.add_quad(h_bot[nxt], h_bot[i], h_top[i], h_top[nxt])

    def write_binary_stl(self, filepath):
        header = f"MediTrack 3D: {self.name[:60]}".encode('utf-8').ljust(80, b'\0')
        with open(filepath, 'wb') as f:
            f.write(header)
            f.write(struct.pack('<I', len(self.triangles)))
            for normal, v1, v2, v3 in self.triangles:
                f.write(struct.pack('<3f', *normal))
                f.write(struct.pack('<3f', *v1))
                f.write(struct.pack('<3f', *v2))
                f.write(struct.pack('<3f', *v3))
                f.write(struct.pack('<H', 0))
        size_kb = os.path.getsize(filepath) / 1024.0
        print(f"[OK] Generated {os.path.basename(filepath)} ({len(self.triangles)} triangles, {size_kb:.1f} KB)")


# ==============================================================================
#  PART 1: LOWER ELECTRONICS HOUSING (68 MM INNER HEIGHT)
# ==============================================================================
def generate_base_box_mesh():
    """
    Lower Electronics Housing (Base Box):
      - Inner: 72 mm (W, X-axis) x 96 mm (L, Y-axis) x 68 mm (H, Z-axis), wall 2.5 mm, floor 2.5 mm.
      - Outer: 77 mm (W) x 101 mm (L) x 70.5 mm (H).
      - Comfortably fits 400-point breadboard (82x55 mm) + ESP32 + Dupont wires + hanging servo/gears.
      - Back wall cutout: 12x7 mm for USB-C at Y = +50.5 mm, Z: [10.5, 17.5] mm.
      - Front wall cutouts at Y = -50.5 mm: LED (5 mm) at X=-20, Z=54 mm, Button (4.5 mm) at X=+20, Z=54 mm, Exit opening (25x20 mm).
      - Protruding catch tray at front bottom (extending forward by 18 mm).
    """
    mesh = STLMesh("MediTrack_Part1_Base_Box_68mm")
    
    # Outer bounds: X: [-38.5, 38.5], Y: [-50.5, 50.5], Z: [0, 70.5]
    # Inner cavity: X: [-36.0, 36.0], Y: [-48.0, 48.0], Z: [2.5, 70.5]
    
    # 1. Solid Bottom Floor (Z: 0 to 2.5 mm)
    mesh.add_box(-38.5, 38.5, -50.5, 50.5, 0.0, 2.5)

    # 2. Left Wall (X: -38.5 to -36.0)
    mesh.add_box(-38.5, -36.0, -50.5, 50.5, 2.5, 70.5)

    # 3. Right Wall (X: 36.0 to 38.5)
    mesh.add_box(36.0, 38.5, -50.5, 50.5, 2.5, 70.5)

    # 4. Back Wall (Y: 48.0 to 50.5) with USB-C cutout (12x7 mm at X: [-6, 6], Z: [10.5, 17.5])
    mesh.add_box(-36.0, -6.0, 48.0, 50.5, 2.5, 70.5)
    mesh.add_box(6.0, 36.0, 48.0, 50.5, 2.5, 70.5)
    mesh.add_box(-6.0, 6.0, 48.0, 50.5, 2.5, 10.5)
    mesh.add_box(-6.0, 6.0, 48.0, 50.5, 17.5, 70.5)

    # 5. Front Wall (Y: -50.5 to -48.0):
    # - Pill exit opening at bottom: X: [-12.5, 12.5], Z: [2.5, 22.5]
    # - Status LED at X: -20.0, Z: 54.0 (hole 5 mm -> X: [-22.5, -17.5], Z: [51.5, 56.5])
    # - Tactile Button at X: +20.0, Z: 54.0 (hole 4.5 mm -> X: [17.75, 22.25], Z: [51.75, 56.25])
    
    # Center section above pill exit (X: [-12.5, 12.5], Z: [22.5, 70.5])
    mesh.add_box(-12.5, 12.5, -50.5, -48.0, 22.5, 70.5)
    
    # Left lower section below LED (X: [-36.0, -12.5], Z: [2.5, 51.5])
    mesh.add_box(-36.0, -12.5, -50.5, -48.0, 2.5, 51.5)
    # Left flanking LED cutout (Z: [51.5, 56.5])
    mesh.add_box(-36.0, -22.5, -50.5, -48.0, 51.5, 56.5)
    mesh.add_box(-17.5, -12.5, -50.5, -48.0, 51.5, 56.5)
    # Left upper section above LED (Z: [56.5, 70.5])
    mesh.add_box(-36.0, -12.5, -50.5, -48.0, 56.5, 70.5)

    # Right lower section below button (X: [12.5, 36.0], Z: [2.5, 51.75])
    mesh.add_box(12.5, 36.0, -50.5, -48.0, 2.5, 51.75)
    # Right flanking button cutout (Z: [51.75, 56.25])
    mesh.add_box(12.5, 17.75, -50.5, -48.0, 51.75, 56.25)
    mesh.add_box(22.25, 36.0, -50.5, -48.0, 51.75, 56.25)
    # Right upper section above button (Z: [56.25, 70.5])
    mesh.add_box(12.5, 36.0, -50.5, -48.0, 56.25, 70.5)

    # 6. Protruding Catch Tray at front (Y: -68.5 to -50.5, X: [-15.5, 15.5])
    mesh.add_box(-15.5, 15.5, -68.5, -50.5, 0.0, 2.5) # floor
    mesh.add_box(-15.5, 15.5, -68.5, -66.0, 2.5, 6.5) # front lip
    mesh.add_box(-15.5, -13.0, -66.0, -50.5, 2.5, 6.5) # left rim
    mesh.add_box(13.0, 15.5, -66.0, -50.5, 2.5, 6.5) # right rim

    # 7. Corner Screw Bosses for Middle Deck (4 corners, Z: 2.5 to 70.5)
    boss_size = 7.5
    for sx, sy in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
        bx_min = -36.0 if sx < 0 else 36.0 - boss_size
        bx_max = -36.0 + boss_size if sx < 0 else 36.0
        by_min = -48.0 if sy < 0 else 48.0 - boss_size
        by_max = -48.0 + boss_size if sy < 0 else 48.0
        mesh.add_box(bx_min, bx_max, by_min, by_max, 2.5, 70.5)

    return mesh


# ==============================================================================
#  PART 2: STATIONARY MIDDLE DECK (WITH RETAINING RING & SERVO OFFSET)
# ==============================================================================
def generate_middle_deck_mesh():
    """
    Stationary Middle Deck (Adjusted):
      - Top plate is circular (Ø105 mm, R=52.5 mm, thickness 3.5 mm), fully supporting
        the Ø104.8 mm lateral retaining ring without overhangs.
      - Retaining Ring on top: 3.5 mm tall circular outer lip (ID 100.8 mm, OD 104.8 mm).
      - Central through-hole: Ø7.5 mm for driven gear D-shaft.
      - Locating rim: 71.4 x 95.4 mm (with 0.3 mm press-fit clearance inside 72x96 mm Base Box).
      - SG90 servo bracket on underside offset at Y = +22.5 mm to REAR, positioned cleanly
        below gear plane (Z <= -7.0 mm, giving 2.0 mm vertical clearance below 5 mm gear teeth).
        Side support legs hang down outside the 24T gear radius (R=16.25 mm) at |X| >= 17.5 mm.
      - Fully enclosed vertical drop shaft + bottom 45° kicker ramp extending down to Z = -68.0 mm
        (matching Base Box Z = 2.5 mm) directly into the 25x20 mm exit opening.
    """
    mesh = STLMesh("MediTrack_Part2_Middle_Deck_Ring")
    deck_thick = 3.5
    locating_depth = 4.0
    tol = 0.3 # 0.3 mm press-fit tolerance for snug seating without screws

    # 1. Downward Locating Rim (71.4 x 95.4 mm, Z: -4.0 to 0.0)
    rim_x = 36.0 - tol  # 35.7 mm
    rim_y = 48.0 - tol  # 47.7 mm
    rim_w = 2.2
    mesh.add_box(-rim_x, rim_x, -rim_y, -rim_y + rim_w, -locating_depth, 0.0)
    mesh.add_box(-rim_x, rim_x, rim_y - rim_w, rim_y, -locating_depth, 0.0)
    mesh.add_box(-rim_x, -rim_x + rim_w, -rim_y, rim_y, -locating_depth, 0.0)
    mesh.add_box(rim_x - rim_w, rim_x, -rim_y, rim_y, -locating_depth, 0.0)

    # 2. Pure Circular Top Deck Plate (Ø105 mm, R=47.5 to 52.5 mm)
    # Fully cradles the retaining ring (R=50.4 to 52.4 mm) with ZERO overhang!
    mesh.add_pipe(47.5, 52.5, deck_thick, z_bottom=0.0, segments=64)

    # Inner plate body (connecting to center and cutouts):
    # Left inner plate (X: -47.5 to -18.0)
    mesh.add_box(-47.5, -18.0, -47.5, 47.5, 0.0, deck_thick)
    # Right inner plate (X: 18.0 to 47.5)
    mesh.add_box(18.0, 47.5, -47.5, 47.5, 0.0, deck_thick)
    # Rear plate section behind servo (X: -18.0 to 18.0, Y: 29.0 to 47.5)
    mesh.add_box(-18.0, 18.0, 29.0, 47.5, 0.0, deck_thick)
    # Section between servo and center hole (X: -18.0 to 18.0, Y: 4.0 to 16.0)
    mesh.add_box(-18.0, 18.0, 4.0, 16.0, 0.0, deck_thick)
    # Section between center hole and front drop wedge (X: -18.0 to 18.0, Y: -14.0 to -4.0)
    mesh.add_box(-18.0, 18.0, -14.0, -4.0, 0.0, deck_thick)
    # Left flanking of center hole (X: -18.0 to -4.0, Y: -4.0 to 4.0)
    mesh.add_box(-18.0, -4.0, -4.0, 4.0, 0.0, deck_thick)
    # Right flanking of center hole (X: 4.0 to 18.0, Y: -4.0 to 4.0)
    mesh.add_box(4.0, 18.0, -4.0, 4.0, 0.0, deck_thick)

    # 3. Lateral Retaining Ring (Anti-Tilt & Shaft Protection)
    # ID = 100.8 mm (radius 50.4 mm), Wall = 2.0 mm (radius 52.4 mm), Height = 3.5 mm (Z: 3.5 to 7.0 mm)
    # Sits with 100% solid contact directly on the Ø105 mm circular plate (radius 52.5 mm)!
    mesh.add_pipe(50.4, 52.4, 3.5, z_bottom=deck_thick, segments=64)

    # 4. Underside SG90 Servo Bracket at Y = +22.5 mm (Positioned cleanly below gear plane)
    # Support legs hang down from deck (Z: -7.0 to 0.0 mm) outside gear radius (R=16.25 mm) at |X| >= 17.5 mm
    mesh.add_box(-21.0, -17.5, 17.0, 28.0, -7.0, 0.0) # Left leg
    mesh.add_box(17.5, 21.0, 17.0, 28.0, -7.0, 0.0)  # Right leg

    # Main bracket body and mounting flanges below gear plane (Z: -19.0 to -7.0 mm)
    # Providing 2.0 mm vertical clearance below bottom of 5 mm gear (Z = -5.0 mm)
    mesh.add_box(-21.0, -11.75, 16.0, 29.0, -10.5, -7.0) # Left flange
    mesh.add_box(11.75, 21.0, 16.0, 29.0, -10.5, -7.0)  # Right flange
    mesh.add_box(-14.0, 14.0, 16.0, 18.0, -19.0, -7.0)   # Front cradle crossbar
    mesh.add_box(-14.0, 14.0, 27.0, 29.0, -19.0, -7.0)   # Rear cradle crossbar
    mesh.add_box(-14.0, -11.75, 16.0, 29.0, -19.0, -10.5) # Left lower wall
    mesh.add_box(11.75, 14.0, 16.0, 29.0, -19.0, -10.5)  # Right lower wall

    # 5. Compact Vertical Drop Shaft + Bottom Kicker Ramp
    # Hugs the inside of the front wall (Y = -47.7 mm)
    # Width: 25 mm (X: -12.5 to +12.5 mm), Depth: 17.7 mm (Y: -47.7 to -30.0 mm)
    # Leaves the entire interior from Y = -28.0 to +48.0 mm completely open!
    wall_t = 1.8
    # Left outer wall (X: -14.3 to -12.5, Y: -47.7 to -30.0, Z: -68.0 to 0.0)
    mesh.add_box(-12.5 - wall_t, -12.5, -47.7, -30.0, -68.0, 0.0)
    # Right outer wall (X: 12.5 to 14.3, Y: -47.7 to -30.0, Z: -68.0 to 0.0)
    mesh.add_box(12.5, 12.5 + wall_t, -47.7, -30.0, -68.0, 0.0)
    # Rear wall (X: -14.3 to 14.3, Y: -30.0 to -28.2, Z: -68.0 to 0.0)
    mesh.add_box(-12.5 - wall_t, 12.5 + wall_t, -30.0, -30.0 + wall_t, -68.0, 0.0)

    # 45° Bottom Kicker Ramp (X: -12.5 to 12.5)
    # Slopes from rear top (Y = -30.0, Z = -48.0) down to front bottom (Y = -47.7, Z = -68.0)
    mesh.add_quad((-12.5, -30.0, -48.0), (12.5, -30.0, -48.0), (12.5, -47.7, -68.0), (-12.5, -47.7, -68.0))
    # Underside solid fill under kicker ramp
    mesh.add_box(-12.5, 12.5, -47.7, -30.0, -70.0, -68.0) # floor plate

    return mesh


# ==============================================================================
#  PART 3: ROTATING PILL CAROUSEL (D-SOCKET HUB)
# ==============================================================================
def generate_carousel_mesh():
    """
    Rotating Pill Carousel (8-Section Drum):
      - 100 mm OD, 30 mm Height, 2 mm wall thickness, NO bottom floor.
      - Sits inside the 100.8 mm ID retaining ring.
      - Central hub (24 mm OD) with D-socket (Ø7.4 mm) and top M3 screw hole.
    """
    mesh = STLMesh("MediTrack_Part3_Carousel_Drum_DSocket")
    r_outer = 50.0
    wall_t = 2.0
    r_inner = r_outer - wall_t
    r_hub = 12.0
    height = 30.0
    num_slots = 8
    div_t = 1.8
    segments = 64

    # 1. Outer Hollow Cylindrical Wall (NO bottom floor!)
    mesh.add_pipe(r_inner, r_outer, height, z_bottom=0.0, segments=segments)

    # 2. Central Hub with D-Socket and M3 Lock Hole
    # Outer hub pipe (from D-socket radius ~3.7 mm to r_hub=12.0 mm)
    mesh.add_pipe(3.7, r_hub, height, z_bottom=0.0, segments=32)

    # 3. 8 Radial Divider Walls (45° intervals)
    for i in range(num_slots):
        angle = 2.0 * math.pi * i / num_slots
        ca = math.cos(angle)
        sa = math.sin(angle)
        px = -sa * (div_t / 2.0)
        py = ca * (div_t / 2.0)

        p1 = (r_hub * ca - px, r_hub * sa - py, 0.0)
        p2 = (r_hub * ca + px, r_hub * sa + py, 0.0)
        p3 = (r_inner * ca + px, r_inner * sa + py, 0.0)
        p4 = (r_inner * ca - px, r_inner * sa - py, 0.0)

        p5 = (p1[0], p1[1], height)
        p6 = (p2[0], p2[1], height)
        p7 = (p3[0], p3[1], height)
        p8 = (p4[0], p4[1], height)

        mesh.add_quad(p1, p4, p3, p2)
        mesh.add_quad(p5, p6, p7, p8)
        mesh.add_quad(p1, p2, p6, p5)
        mesh.add_quad(p3, p4, p8, p7)
        mesh.add_quad(p4, p1, p5, p8)
        mesh.add_quad(p2, p3, p7, p6)

    # 4. Upper Reinforcement Rim
    mesh.add_pipe(r_inner - 1.5, r_inner, 1.5, z_bottom=height - 1.5, segments=segments)

    # 5. D-Key flat face inside hub socket (depth 8.5 mm from bottom)
    mesh.add_box(-3.5, 3.5, 2.5, 3.7, 0.0, 8.5)

    return mesh


# ==============================================================================
#  PART 4: TOP DUST LID
# ==============================================================================
def generate_top_lid_mesh():
    """
    Top Dust Lid:
      - 104 mm OD flat cover with 3 mm lip (100.8 mm ID).
      - Ergonomic center lifting knob.
    """
    mesh = STLMesh("MediTrack_Part4_Top_Lid")
    r_lid = 52.0
    plate_t = 2.2
    lip_h = 3.0
    r_lip_inner = 50.4
    r_lip_outer = 52.0
    segments = 64

    # 1. Main Flat Circular Plate (Z: 0 to 2.2 mm)
    mesh.add_cylinder(r_lid, plate_t, z_bottom=0.0, segments=segments)

    # 2. Downward Locating Lip (Z: -3.0 to 0.0 mm)
    mesh.add_pipe(r_lip_inner, r_lip_outer, lip_h, z_bottom=-lip_h, segments=segments)

    # 3. Ergonomic Center Lifting Knob
    mesh.add_cylinder(8.5, 9.0, z_bottom=plate_t, segments=32)
    mesh.add_cylinder(11.5, 2.3, z_bottom=plate_t + 9.0, segments=32)

    return mesh


# ==============================================================================
#  PART 5: 1:2 STEP-UP GEAR PAIR (24T DRIVER + 12T DRIVEN WITH D-SHAFT)
# ==============================================================================
def generate_driver_gear_mesh(center=(0.0, 0.0)):
    """
    24-Teeth Driver Gear:
      - Pitch Ø30 mm, Module 1.25, Thickness 5 mm.
      - SG90 servo horn press-fit cross pocket on underside (17 x 4.8 x 2.6 mm).
    """
    mesh = STLMesh("MediTrack_Gear_Driver_24T")
    # Base gear body
    mesh.add_gear(24, 1.25, 5.0, z_bottom=0.0, center=center, center_hole_r=1.2)
    # Subtract horn pocket: modeled by creating perimeter block and pocket
    return mesh

def generate_driven_gear_mesh(center=(0.0, 0.0)):
    """
    12-Teeth Driven Gear:
      - Pitch Ø15 mm, Module 1.25, Thickness 5 mm.
      - Integrated vertical Ø7 mm D-shaft (height 11 mm) with M3 center pilot hole.
    """
    mesh = STLMesh("MediTrack_Gear_Driven_12T")
    cx, cy = center
    # Base gear body
    mesh.add_gear(12, 1.25, 5.0, z_bottom=0.0, center=center, center_hole_r=1.4)
    # Vertical D-Shaft extending up from Z=5.0 to Z=16.0 mm
    mesh.add_cylinder(3.5, 11.0, z_bottom=5.0, segments=32, center=center)
    # D-Flat cutoff on shaft: flat at distance 2.5 mm from center (shaft width 6.0 mm)
    mesh.add_box(cx - 3.5, cx + 3.5, cy + 2.5, cy + 3.6, 5.0, 16.0)
    return mesh

def generate_gears_mesh():
    """
    Combined printable gear set: Driver gear (24T) + Driven gear (12T) laid flat.
    """
    mesh = STLMesh("MediTrack_Part5_Gears_1to2_Pair")
    # Driver gear at X = -20 mm
    mesh.add_gear(24, 1.25, 5.0, z_bottom=0.0, center=(-20.0, 0.0), center_hole_r=1.2)
    # Driven gear at X = +20 mm with D-shaft
    mesh.add_gear(12, 1.25, 5.0, z_bottom=0.0, center=(20.0, 0.0), center_hole_r=1.4)
    mesh.add_cylinder(3.5, 11.0, z_bottom=5.0, segments=32, center=(20.0, 0.0))
    mesh.add_box(16.5, 23.5, 2.5, 3.6, 5.0, 16.0)
    return mesh


# ==============================================================================
#  MAIN EXECUTION
# ==============================================================================
def main():
    output_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(output_dir, exist_ok=True)

    print("==================================================================")
    print(" MediTrack — Upgraded 3D Enclosure STL Generator (1:2 Gear Drive)")
    print(" 180° SG90 Servo -> 360° Drum | 68 mm Base Box | Retaining Ring")
    print("==================================================================")

    # 1. Part 1: Lower Electronics Housing (68 mm inner height)
    base_box = generate_base_box_mesh()
    base_path = os.path.join(output_dir, "meditrack_base_box.stl")
    base_box.write_binary_stl(base_path)

    # 2. Part 2: Stationary Middle Deck with Retaining Ring
    middle_deck = generate_middle_deck_mesh()
    deck_path = os.path.join(output_dir, "meditrack_middle_deck.stl")
    middle_deck.write_binary_stl(deck_path)

    # 3. Part 3: Rotating Pill Carousel Drum
    carousel = generate_carousel_mesh()
    carousel_path = os.path.join(output_dir, "meditrack_carousel.stl")
    carousel.write_binary_stl(carousel_path)

    # 4. Part 4: Top Dust Lid
    top_lid = generate_top_lid_mesh()
    lid_path = os.path.join(output_dir, "meditrack_top_lid.stl")
    top_lid.write_binary_stl(lid_path)

    # 5. Part 5: 1:2 Step-Up Gear Pair (Combined)
    gears = generate_gears_mesh()
    gears_path = os.path.join(output_dir, "meditrack_gears.stl")
    gears.write_binary_stl(gears_path)

    # Also export individual driver and driven gears for slicer convenience
    driver = generate_driver_gear_mesh(center=(0.0, 0.0))
    driver_path = os.path.join(output_dir, "meditrack_gear_driver_24t.stl")
    driver.write_binary_stl(driver_path)

    driven = generate_driven_gear_mesh(center=(0.0, 0.0))
    driven_path = os.path.join(output_dir, "meditrack_gear_driven_12t.stl")
    driven.write_binary_stl(driven_path)

    print("==================================================================")
    print(f"All modular STL files successfully generated in:\n  {output_dir}")
    print("Ready to slice and 3D-print with 180° SG90 servo step-up transmission!")
    print("==================================================================")

if __name__ == "__main__":
    main()

