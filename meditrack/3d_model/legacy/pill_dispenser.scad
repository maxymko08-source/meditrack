// ==============================================================================
//  MediTrack — Modular IoT Smart Pill Dispenser Enclosure (Upgraded 1:2 Gear Drive)
//  Parametric 3D CAD Model for FDM/SLA 3D Printing (OpenSCAD)
//
//  Upgraded Architecture:
//    1. 1:2 Step-Up Gear Drive Under Middle Deck (180° Servo -> 360° Drum):
//       - Driver gear: 24 teeth (pitch Ø30 mm, module 1.25, 5 mm thickness) with SG90 horn pocket.
//         Offset by Y = +22.5 mm from center away from front pill chute.
//       - Driven gear: 12 teeth (pitch Ø15 mm, module 1.25, 5 mm thickness) at center (0, 0).
//         Integrated vertical Ø7 mm D-shaft passing through Ø7.5 mm hole in Middle Deck.
//       - Carousel underside hub press-fits onto D-shaft with top M3 retention screw.
//       - 22.5° servo rotation = 45° drum rotation (covers all 8 compartments).
//    2. Lateral Retaining Ring on Middle Deck:
//       - 3.5 mm tall circular outer lip (ID 100.8 mm, wall 2.0 mm) surrounding Ø100 mm carousel.
//       - Prevents drum tilting and protects center drive shaft from lateral loads.
//    3. Increased Base Box Height:
//       - Inner height increased to 68 mm (outer 70.5 mm) for ample clearance above
//         400-point breadboard (82x55 mm), ESP32 board, hanging servo, gears, and chute.
// ==============================================================================

$fn = 120; // Smooth curves for rendering and slicing

// ==============================================================================
//  CONFIGURATION & SELECTOR
// ==============================================================================
// "all"      - Complete assembled & exploded view
// "base"     - Part 1: Lower Electronics Housing (68 mm inner height)
// "deck"     - Part 2: Stationary Middle Deck with Retaining Ring & Chute
// "carousel" - Part 3: Rotating Pill Carousel (D-socket hub)
// "lid"      - Part 4: Top Dust Lid
// "gears"    - Part 5: 1:2 Step-Up Gear Pair (24T Driver + 12T Driven with D-shaft)
PART = "all";

// ==============================================================================
//  GLOBAL PARAMETRIC SPECIFICATIONS (All units in millimeters [mm])
// ==============================================================================

// --- Manufacturing Tolerances ---
TOLERANCE = 0.4;                     // 0.4 mm tolerance for mating fits

// --- Part 1: Lower Electronics Housing (Base Box) ---
BASE_INNER_W     = 72.0;             // Inner width  (X-axis, >= 70 mm, fits 55 mm breadboard)
BASE_INNER_L     = 96.0;             // Inner length (Y-axis, >= 95 mm, fits 82 mm breadboard)
BASE_INNER_H     = 68.0;             // Upgraded inner height: 68 mm
BASE_WALL_T      = 2.5;              // Wall thickness (2.5 mm)
BASE_FLOOR_T     = 2.5;              // Floor thickness (2.5 mm)
CORNER_RADIUS    = 4.0;              // Outer corner fillet radius

// Derived Outer Dimensions:
BASE_OUTER_W     = BASE_INNER_W + 2 * BASE_WALL_T; // 77.0 mm (X-axis)
BASE_OUTER_L     = BASE_INNER_L + 2 * BASE_WALL_T; // 101.0 mm (Y-axis)
BASE_OUTER_H     = BASE_INNER_H + BASE_FLOOR_T;    // 70.5 mm (Z-axis)

// Cutouts:
USB_CUTOUT_W     = 12.0;             // USB Type-C cutout width
USB_CUTOUT_H     = 7.0;              // USB Type-C cutout height
USB_CENTER_Z     = 14.0;             // Height aligned with ESP32 on breadboard

LED_HOLE_DIA     = 5.0;              // 5 mm hole for status LED
LED_POS_X        = -20.0;            // Left front panel (clears front chute)
LED_POS_Z        = 54.0;             // Ergonomic upper front panel

BTN_HOLE_DIA     = 4.5;              // 4.5 mm hole for 6x6x12 mm button stem
BTN_POS_X        = 20.0;             // Right front panel (clears front chute)
BTN_POS_Z        = 54.0;             // Ergonomic upper front panel

EXIT_HOLE_W      = 25.0;             // Pill exit width
EXIT_HOLE_H      = 20.0;             // Pill exit height
EXIT_POS_Z       = BASE_FLOOR_T;     // Aligned with bottom floor

TRAY_PROTRUSION  = 18.0;             // Catch tray forward extension
TRAY_LIP_H       = 6.0;              // Catch tray lip height
TRAY_WALL_T      = 2.5;              // Catch tray wall thickness

// --- 1:2 Gear Drive Specifications (Module 1.25 mm) ---
GEAR_MODULE      = 1.25;             // Module 1.25 mm
GEAR_THICKNESS   = 5.0;              // Gear face thickness (5.0 mm)
GEAR_DRIVER_TEETH= 24;               // 24 teeth (Pitch Ø30.0 mm)
GEAR_DRIVEN_TEETH= 12;               // 12 teeth (Pitch Ø15.0 mm)
GEAR_DRIVER_PD   = GEAR_MODULE * GEAR_DRIVER_TEETH; // 30.0 mm
GEAR_DRIVEN_PD   = GEAR_MODULE * GEAR_DRIVEN_TEETH; // 15.0 mm
GEAR_CENTER_DIST = (GEAR_DRIVER_PD + GEAR_DRIVEN_PD) / 2; // 22.5 mm

// Drive D-Shaft:
SHAFT_DIA        = 7.0;              // Shaft diameter: 7.0 mm
SHAFT_FLAT_D     = 6.0;              // D-flat width: 6.0 mm (1 mm flat cut)
SHAFT_HEIGHT     = 12.0;             // Height extending through middle deck (4.5 mm deck + 7.5 mm hub socket)
DECK_SHAFT_HOLE  = 7.5;              // Central hole in deck (Ø7.5 mm)

// Servo SG90 Specs:
SERVO_BODY_L     = 23.0;             // Servo cutout length (23 mm)
SERVO_BODY_W     = 12.5;             // Servo cutout width (12.5 mm)
SERVO_SCREW_DIST = 27.5;             // Distance between SG90 mounting holes
SERVO_SCREW_DIA  = 2.0;              // M2 screw hole diameter
SERVO_SHAFT_OFF  = 5.5;              // SG90 shaft offset from body center

// --- Part 2: Middle Deck ---
DECK_PLATE_T     = 4.5;              // Increased top plate thickness: 4.5 mm (solid continuous deck)
DECK_LOCATING_H  = 4.0;              // Depth of downward locating rim
SCREW_BOSS_DIA   = 7.5;              // Corner screw boss diameter
SCREW_HOLE_DIA   = 3.2;              // M3 screw hole diameter

// Lateral Retaining Ring (Anti-Tilt):
RETAINING_RING_H = 3.5;              // Height of retaining ring above deck
RETAINING_RING_ID= 100.8;            // Inner diameter (100 mm carousel + 2*0.4 mm tol)
RETAINING_RING_T = 2.0;              // Ring wall thickness (2.0 mm)
RETAINING_RING_R = RETAINING_RING_ID / 2; // 50.4 mm inner radius

// Full-Sector Pill Drop Hole (Exact 43-degree sector matching compartment inner footprint):
WEDGE_R_INNER    = 11.0;             // 11.0 mm (just outside central hub)
WEDGE_R_OUTER    = 47.5;             // 47.5 mm (strictly inside drum 48 mm inner wall)
WEDGE_ANGLE      = 43.0;             // 43.0 degrees (exact compartment floor opening)

// Internal Chute:
CHUTE_ANGLE      = 42.0;             // Chute slope down to front exit opening

// --- Part 3: Rotating Pill Carousel (8-Section Drum) ---
CAROUSEL_OD      = 100.0;            // Outer diameter: 100 mm
CAROUSEL_R       = CAROUSEL_OD / 2;  // Outer radius: 50 mm
CAROUSEL_H       = 30.0;             // Height: 30 mm
CAROUSEL_WALL_T  = 2.0;              // Outer wall thickness: 2 mm
NUM_SLOTS        = 8;                // 8 pie-slice compartments
DIVIDER_T        = 1.8;              // Radial divider thickness
HUB_R            = 12.0;             // Central hub radius (24 mm OD)

// --- Part 4: Top Dust Lid ---
LID_OD           = 104.0;            // Outer diameter: 104 mm
LID_R            = LID_OD / 2;       // 52 mm radius
LID_PLATE_T      = 2.2;              // Lid plate thickness
LID_LIP_H        = 3.0;              // 3 mm downward locating lip
LID_LIP_T        = 1.8;              // Lip wall thickness
LID_LIP_INNER_R  = (CAROUSEL_OD / 2) + TOLERANCE; // 50.4 mm


// ==============================================================================
//  HELPER MODULES: ROUNDED BOX & SPUR GEAR GENERATOR
// ==============================================================================

module rounded_box(x_size, y_size, z_size, r, center_xy=true) {
    tx = center_xy ? -x_size/2 : 0;
    ty = center_xy ? -y_size/2 : 0;
    translate([tx, ty, 0]) {
        hull() {
            translate([r, r, 0]) cylinder(r=r, h=z_size);
            translate([x_size - r, r, 0]) cylinder(r=r, h=z_size);
            translate([x_size - r, y_size - r, 0]) cylinder(r=r, h=z_size);
            translate([r, y_size - r, 0]) cylinder(r=r, h=z_size);
        }
    }
}

module sector_wedge(r_in, r_out, angle, h) {
    rotate([0, 0, -angle/2 - 90])
    rotate_extrude(angle=angle)
        translate([r_in, 0, 0])
            square([r_out - r_in, h]);
}

// Parametric Spur Gear Generator
module spur_gear(num_teeth, module_val, thickness) {
    pitch_r = (num_teeth * module_val) / 2;
    addendum = 1.0 * module_val;
    dedendum = 1.25 * module_val;
    tip_r = pitch_r + addendum;
    root_r = pitch_r - dedendum;
    tooth_angle = 360 / num_teeth;
    half_tooth = tooth_angle / 4;

    linear_extrude(height = thickness) {
        union() {
            circle(r = root_r);
            for (i = [0:num_teeth-1]) {
                rotate([0, 0, i * tooth_angle]) {
                    polygon(points=[
                        [root_r * cos(-half_tooth*1.4), root_r * sin(-half_tooth*1.4)],
                        [pitch_r * cos(-half_tooth), pitch_r * sin(-half_tooth)],
                        [tip_r * cos(-half_tooth*0.6), tip_r * sin(-half_tooth*0.6)],
                        [tip_r * cos(half_tooth*0.6), tip_r * sin(half_tooth*0.6)],
                        [pitch_r * cos(half_tooth), pitch_r * sin(half_tooth)],
                        [root_r * cos(half_tooth*1.4), root_r * sin(half_tooth*1.4)]
                    ]);
                }
            }
        }
    }
}

// D-profile shaft / key
module d_shaft(dia, flat_dist, height) {
    difference() {
        cylinder(d = dia, h = height);
        translate([flat_dist - dia/2, -dia, -0.5])
            cube([dia, dia * 2, height + 1]);
    }
}


// ==============================================================================
//  PART 1: LOWER ELECTRONICS HOUSING (BASE BOX, 68 MM HEIGHT)
// ==============================================================================
module base_electronics_box() {
    difference() {
        union() {
            // Main solid rounded outer body (77 mm W x 101 mm L x 70.5 mm H)
            rounded_box(BASE_OUTER_W, BASE_OUTER_L, BASE_OUTER_H, CORNER_RADIUS, center_xy=true);

            // Protruding catch tray at front (Y < -BASE_OUTER_L/2)
            translate([-EXIT_HOLE_W/2 - TRAY_WALL_T, -BASE_OUTER_L/2 - TRAY_PROTRUSION, 0]) {
                difference() {
                    hull() {
                        translate([CORNER_RADIUS, CORNER_RADIUS, 0])
                            cylinder(r=CORNER_RADIUS, h=TRAY_LIP_H);
                        translate([EXIT_HOLE_W + 2*TRAY_WALL_T - CORNER_RADIUS, CORNER_RADIUS, 0])
                            cylinder(r=CORNER_RADIUS, h=TRAY_LIP_H);
                        translate([0, TRAY_PROTRUSION - 1, 0])
                            cube([EXIT_HOLE_W + 2*TRAY_WALL_T, 1, TRAY_LIP_H]);
                    }
                    translate([TRAY_WALL_T, TRAY_WALL_T, BASE_FLOOR_T])
                        rounded_box(EXIT_HOLE_W, TRAY_PROTRUSION, TRAY_LIP_H + 1, 2.0, center_xy=false);
                }
            }

            // 4 Corner Screw Bosses for fastening Middle Deck
            for (sx = [-1, 1]) {
                for (sy = [-1, 1]) {
                    translate([sx * (BASE_INNER_W/2 - SCREW_BOSS_DIA/2), sy * (BASE_INNER_L/2 - SCREW_BOSS_DIA/2), BASE_FLOOR_T]) {
                        cylinder(r=SCREW_BOSS_DIA/2, h=BASE_INNER_H);
                    }
                }
            }
        }

        // 1. Inner Cavity for Breadboard (82x55 mm) + ESP32 + Wire headroom (68 mm high)
        translate([0, 0, BASE_FLOOR_T])
            rounded_box(BASE_INNER_W, BASE_INNER_L, BASE_INNER_H + 2, CORNER_RADIUS - 1, center_xy=true);

        // 2. Back Wall Cutout: 12 x 7 mm for USB Type-C Cable at Y = +BASE_OUTER_L/2
        translate([0, BASE_OUTER_L/2, USB_CENTER_Z])
            cube([USB_CUTOUT_W, BASE_WALL_T * 3, USB_CUTOUT_H], center=true);

        // 3. Front Panel Cutouts at Y = -BASE_OUTER_L/2:
        // A. 5 mm Status LED Hole (Z = 54 mm)
        translate([LED_POS_X, -BASE_OUTER_L/2, LED_POS_Z])
            rotate([90, 0, 0])
                cylinder(r=LED_HOLE_DIA/2, h=BASE_WALL_T * 3, center=true);

        // B. 4.5 mm Push-Button Stem Hole (Z = 54 mm)
        translate([BTN_POS_X, -BASE_OUTER_L/2, BTN_POS_Z])
            rotate([90, 0, 0])
                cylinder(r=BTN_HOLE_DIA/2, h=BASE_WALL_T * 3, center=true);

        // C. Rectangular Pill Exit Opening (25 mm W x 20 mm H)
        translate([-EXIT_HOLE_W/2, -BASE_OUTER_L/2 - 1, EXIT_POS_Z])
            cube([EXIT_HOLE_W, BASE_WALL_T + 2, EXIT_HOLE_H]);

        // 4. Screw pilot holes in the 4 corner bosses (M3)
        for (sx = [-1, 1]) {
            for (sy = [-1, 1]) {
                translate([sx * (BASE_INNER_W/2 - SCREW_BOSS_DIA/2), sy * (BASE_INNER_L/2 - SCREW_BOSS_DIA/2), BASE_OUTER_H - 14]) {
                    cylinder(r=SCREW_HOLE_DIA/2, h=16);
                }
            }
        }
    }
}


// ==============================================================================
//  PART 2: STATIONARY MIDDLE DECK (CIRCULAR Ø105 MM, 4.5 MM SOLID PLATE & TAPERED FUNNEL)
// ==============================================================================
module middle_deck_with_chute() {
    DECK_PRESSFIT_TOL = 0.3; // 0.3 mm press-fit tolerance for snug lid seating without screws

    difference() {
        union() {
            // 1. Pure Circular Top Deck Plate (Ø105 mm, 4.5 mm thick)
            // Increased to 4.5 mm: 100% solid continuous top surface with zero slits or gear penetrations
            cylinder(d = 105.0, h = DECK_PLATE_T);

            // 2. Lateral Retaining Ring (Anti-Tilt & Shaft Protection)
            // 3.5 mm tall circular outer lip (ID 100.8 mm, OD 104.8 mm, fully supported by Ø105 mm plate)
            translate([0, 0, DECK_PLATE_T])
                difference() {
                    cylinder(r = RETAINING_RING_R + RETAINING_RING_T, h = RETAINING_RING_H);
                    translate([0, 0, -0.5])
                        cylinder(r = RETAINING_RING_R, h = RETAINING_RING_H + 1);
                }

            // 3. Downward Locating Rim (71.4 x 95.4 mm with 0.3 mm press-fit clearance)
            translate([0, 0, -DECK_LOCATING_H])
                difference() {
                    rounded_box(BASE_INNER_W - 2*DECK_PRESSFIT_TOL, BASE_INNER_L - 2*DECK_PRESSFIT_TOL, DECK_LOCATING_H, CORNER_RADIUS - 1, center_xy=true);
                    translate([0, 0, -1])
                        rounded_box(BASE_INNER_W - 2*DECK_PRESSFIT_TOL - 4, BASE_INNER_L - 2*DECK_PRESSFIT_TOL - 4, DECK_LOCATING_H + 2, CORNER_RADIUS - 2, center_xy=true);
                }

            // 4. Underside SG90 Servo Bracket (Offset to REAR at Y = +22.5 mm)
            // Positioned cleanly below the gear plane (Z <= -7.0 mm) giving 2.0 mm vertical clearance
            // Side support legs hang outside 24T gear radius (R=16.25 mm) at |X| >= 17.5 mm
            translate([0, GEAR_CENTER_DIST, 0]) {
                // Two side support legs anchored to deck plate outside gear radius (R=16.25 mm)
                for (sx = [-1, 1]) {
                    translate([sx * 19.5, 0, -3.5])
                        cube([4.0, SERVO_BODY_W + 5.5, 7.0], center=true);
                }
                // Main servo cradle and mounting flanges located below gear plane (Z = -7.0 to -19.0 mm)
                translate([0, 0, -13.0]) {
                    difference() {
                        // Solid outer bracket body
                        cube([SERVO_BODY_L + 16.0, SERVO_BODY_W + 5.5, 12.0], center=true);
                        // Servo body cavity (23.4 x 12.9 mm) centered under the shaft
                        translate([0, 0, 0])
                            cube([SERVO_BODY_L + TOLERANCE, SERVO_BODY_W + TOLERANCE, 14.0], center=true);
                        // M2 mounting screw holes at X = +/- 13.75 mm
                        for (sx = [-1, 1]) {
                            translate([sx * SERVO_SCREW_DIST/2, 0, 0])
                                cylinder(r = SERVO_SCREW_DIA/2, h = 14.0, center=true);
                        }
                    }
                }
            }

            // 5. Downward Integrated Tapered Funnel Chute + Bottom Kicker Ramp
            // Matches full 43° sector at top (R=10 to 48.5 mm, ~38 mm outer width)
            // Tapers smoothly down to 25x20 mm front exit opening with 45° kicker ramp
            // Zero flat shelves or horizontal ledges!
            difference() {
                // Outer Tapered Funnel Housing (hull between top sector profile and bottom exit box)
                hull() {
                    // Top outer sector collar matching the 43° sector opening with ~1.5 mm wall
                    translate([0, 0, -1.5])
                        sector_wedge(10.0, 48.5, WEDGE_ANGLE + 2.0, 1.5);
                    // Bottom outer box at the exit opening (Z = -68 to -46 mm)
                    translate([-EXIT_HOLE_W/2 - 1.8, -BASE_INNER_L/2 - 0.5, -BASE_INNER_H])
                        cube([EXIT_HOLE_W + 3.6, 18.0 + 1.8 + 0.5, EXIT_HOLE_H + 2.0]);
                }

                // Inner Hollow: Smooth Tapered Funnel (hull from 43° sector down to 25x18 mm cavity)
                hull() {
                    // Top inner sector void matching exact 43° compartment footprint
                    translate([0, 0, -0.5])
                        sector_wedge(WEDGE_R_INNER, WEDGE_R_OUTER, WEDGE_ANGLE, 2.0);
                    // Lower transition at top of kicker ramp (Z = -48 mm)
                    translate([-EXIT_HOLE_W/2, -BASE_INNER_L/2 - 1.0, -BASE_INNER_H + EXIT_HOLE_H])
                        cube([EXIT_HOLE_W, 18.0 + 1.0, 2.0]);
                }

                // Front exit opening window through the front wall (Z = -68 to -48 mm)
                translate([-EXIT_HOLE_W/2, -BASE_INNER_L/2 - 3.0, -BASE_INNER_H])
                    cube([EXIT_HOLE_W, 6.0, EXIT_HOLE_H]);

                // 45° Bottom Kicker Ramp (Slopes forward out to the catch tray)
                hull() {
                    translate([-EXIT_HOLE_W/2, -BASE_INNER_L/2 - 1.0, -BASE_INNER_H])
                        cube([EXIT_HOLE_W, 0.1, 0.1]);
                    translate([-EXIT_HOLE_W/2, -BASE_INNER_L/2 + 18.0, -BASE_INNER_H + EXIT_HOLE_H])
                        cube([EXIT_HOLE_W, 0.1, 0.1]);
                    translate([-EXIT_HOLE_W/2, -BASE_INNER_L/2 - 1.0, -BASE_INNER_H + EXIT_HOLE_H])
                        cube([EXIT_HOLE_W, 18.0 + 1.0, 0.1]);
                }
            }
        }

        // --- CUTOUTS IN MIDDLE DECK ---
        // 1. Central Hole for Driven Gear D-Shaft (Ø7.5 mm)
        cylinder(d = DECK_SHAFT_HOLE, h = DECK_PLATE_T * 3, center=true);

        // 2. Full-Sector Pill Drop Hole (Exact 43° sector matching compartment inner footprint)
        // R_inner = 11.0 mm (just outside hub), R_outer = 47.5 mm (strictly inside 48 mm drum wall)
        translate([0, 0, -1])
            sector_wedge(WEDGE_R_INNER, WEDGE_R_OUTER, WEDGE_ANGLE, DECK_PLATE_T + 2);
    }
}


// ==============================================================================
//  PART 3: ROTATING PILL CAROUSEL (D-SOCKET HUB & M3 LOCK SCREW)
// ==============================================================================
module carousel_drum_8slots() {
    difference() {
        union() {
            // 1. Outer Hollow Cylinder (100 mm OD, 30 mm Height, NO bottom floor)
            difference() {
                cylinder(r=CAROUSEL_R, h=CAROUSEL_H);
                translate([0, 0, -1])
                    cylinder(r=CAROUSEL_R - CAROUSEL_WALL_T, h=CAROUSEL_H + 2);
            }

            // 2. Central Hub Cylinder (24 mm OD)
            cylinder(r=HUB_R, h=CAROUSEL_H);

            // 3. 8 Radial Divider Walls (45° intervals)
            for (i = [0:NUM_SLOTS-1]) {
                rotate([0, 0, i * (360 / NUM_SLOTS)])
                translate([0, -DIVIDER_T/2, 0])
                    cube([CAROUSEL_R, DIVIDER_T, CAROUSEL_H]);
            }

            // 4. Upper Reinforcement Rim
            translate([0, 0, CAROUSEL_H - 1.5])
                difference() {
                    cylinder(r=CAROUSEL_R, h=1.5);
                    translate([0, 0, -0.5])
                        cylinder(r=CAROUSEL_R - CAROUSEL_WALL_T - 1.0, h=2.5);
                }
        }

        // --- UNDERSIDE D-SOCKET (Mates to Driven Gear D-Shaft) ---
        // Ø7.4 mm with 6.4 mm flat depth (0.4 mm tolerance)
        translate([0, 0, -0.1])
            d_shaft(SHAFT_DIA + TOLERANCE, SHAFT_FLAT_D + TOLERANCE, 8.5);

        // --- TOP M3 RETENTION SCREW HOLE ---
        // Locks drum vertically onto D-shaft
        translate([0, 0, 7.0])
            cylinder(r = SCREW_HOLE_DIA/2, h = CAROUSEL_H);
        translate([0, 0, CAROUSEL_H - 4.0])
            cylinder(r = 3.2, h = 5.0); // M3 screw head counterbore

        // --- COMPARTMENT EMBOSSED LABELS (0 to 7) ---
        for (i = [0:NUM_SLOTS-1]) {
            rotate([0, 0, i * (360 / NUM_SLOTS) + 22.5])
            translate([CAROUSEL_R - 9.0, -2.5, CAROUSEL_H - 0.8])
                linear_extrude(1.2)
                    text(str(i), size=4.5, font="Liberation Sans:style=Bold");
        }
    }
}


// ==============================================================================
//  PART 4: TOP DUST LID
// ==============================================================================
module top_dust_lid() {
    difference() {
        union() {
            // Flat Circular Cover (104 mm OD)
            cylinder(r=LID_R, h=LID_PLATE_T);

            // Downward Locating Lip (3 mm Height, with 0.4 mm clearance)
            translate([0, 0, -LID_LIP_H])
                difference() {
                    cylinder(r=LID_LIP_INNER_R + LID_LIP_T, h=LID_LIP_H);
                    translate([0, 0, -0.5])
                        cylinder(r=LID_LIP_INNER_R, h=LID_LIP_H + 1);
                }

            // Ergonomic Center Lifting Knob
            translate([0, 0, LID_PLATE_T]) {
                cylinder(r1=8.0, r2=10.0, h=10.0);
                translate([0, 0, 10.0])
                    cylinder(r=11.5, h=2.5);
            }
        }

        // Embossed Label on Lid Top
        translate([0, 26, LID_PLATE_T - 0.6])
            linear_extrude(1.0)
                text("MEDITRACK", size=5.5, halign="center", valign="center", font="Liberation Sans:style=Bold");

        translate([0, -26, LID_PLATE_T - 0.6])
            linear_extrude(1.0)
                text("PILL DISPENSER", size=3.5, halign="center", valign="center");
    }
}


// ==============================================================================
//  PART 5: 1:2 STEP-UP GEAR PAIR (PRINTABLE GEAR SET)
// ==============================================================================
module gear_driver_24t() {
    // 24-Teeth Driver Gear (Pitch Ø30 mm, Module 1.25, 5 mm thick)
    difference() {
        spur_gear(GEAR_DRIVER_TEETH, GEAR_MODULE, GEAR_THICKNESS);

        // Underside SG90 Servo Horn Press-fit Pocket
        translate([0, 0, -0.1]) {
            cube([17.0, 4.8, 2.6], center=true);
            cube([4.8, 17.0, 2.6], center=true);
            cylinder(r = 4.0, h = 2.6);
            cylinder(r = 1.2, h = GEAR_THICKNESS + 2); // M2 retention screw hole
        }
    }
}

module gear_driven_12t() {
    // 12-Teeth Driven Gear (Pitch Ø15 mm, Module 1.25, 5 mm thick) + D-Shaft
    union() {
        difference() {
            spur_gear(GEAR_DRIVEN_TEETH, GEAR_MODULE, GEAR_THICKNESS);
            // Center pilot hole for M3 lock screw
            translate([0, 0, -0.5])
                cylinder(r = 1.4, h = GEAR_THICKNESS + SHAFT_HEIGHT + 2);
        }

        // Integrated Vertical D-Shaft (Ø7 mm, extending upward)
        translate([0, 0, GEAR_THICKNESS])
            difference() {
                d_shaft(SHAFT_DIA, SHAFT_FLAT_D, SHAFT_HEIGHT);
                translate([0, 0, SHAFT_HEIGHT - 8.0])
                    cylinder(r = 1.4, h = 9.0); // M3 tap hole
            }
    }
}

module gear_pair_printable() {
    // Both gears laid flat on buildplate for 3D printing
    translate([-20, 0, 0])
        gear_driver_24t();

    translate([20, 0, 0])
        gear_driven_12t();
}


// ==============================================================================
//  ASSEMBLY & RENDER VIEW
// ==============================================================================
if (PART == "all") {
    // 1. Lower Electronics Housing (Base Box)
    color([0.2, 0.45, 0.75, 0.85])
        base_electronics_box();

    // 2. 1:2 Gear Drive under Middle Deck
    translate([0, GEAR_CENTER_DIST, BASE_OUTER_H + 4])
        color([0.9, 0.8, 0.2, 0.95])
            gear_driver_24t();

    translate([0, 0, BASE_OUTER_H + 4])
        color([0.85, 0.5, 0.2, 0.95])
            gear_driven_12t();

    // 3. Stationary Middle Deck with Retaining Ring
    color([0.5, 0.55, 0.6, 0.9])
        translate([0, 0, BASE_OUTER_H + 12])
            middle_deck_with_chute();

    // 4. Rotating Pill Carousel (Drum)
    color([0.95, 0.45, 0.2, 0.9])
        translate([0, 0, BASE_OUTER_H + DECK_PLATE_T + 22])
            carousel_drum_8slots();

    // 5. Top Dust Lid
    color([0.2, 0.75, 0.45, 0.75])
        translate([0, 0, BASE_OUTER_H + DECK_PLATE_T + CAROUSEL_H + 34])
            top_dust_lid();
}
else if (PART == "base") {
    base_electronics_box();
}
else if (PART == "deck") {
    middle_deck_with_chute();
}
else if (PART == "carousel") {
    carousel_drum_8slots();
}
else if (PART == "lid") {
    top_dust_lid();
}
else if (PART == "gears") {
    gear_pair_printable();
}


