from flask import Flask, render_template, request
import json
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2)**2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c  # distance in meters

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            depth = float(request.form["depth"])
            speed = float(request.form["speed"])  # AUV speed through water (m/s)
            battery_capacity = float(request.form["battery_capacity"])
            weight = float(request.form["weight"])  # vehicle weight in kg
            volume = float(request.form.get("volume", 0))  # volume in m^3, optional, default 0

            # Manual current inputs
            current_speed = float(request.form.get("current_speed", 0))  # m/s
            current_dir_deg = float(request.form.get("current_direction", 0))  # degrees from North

            if depth < 0 or speed <= 0 or battery_capacity <= 0 or current_speed < 0 or weight <= 0:
                raise ValueError("Depth ≥ 0; Speed, Battery Capacity, Current Speed and Weight > 0.")

            waypoints_json = request.form.get("waypoints", "[]")
            waypoints = json.loads(waypoints_json)

            if len(waypoints) < 2:
                raise ValueError("Please add at least two waypoints on the map.")

            # Calculate total horizontal distance using Haversine formula
            total_distance = 0
            for i in range(len(waypoints) - 1):
                lat1, lon1 = waypoints[i]
                lat2, lon2 = waypoints[i + 1]
                dist = haversine(lat1, lon1, lat2, lon2)
                total_distance += dist

            # Convert current direction to radians
            current_dir_rad = radians(current_dir_deg)

            # Calculate heading from first to second waypoint (radians from North)
            lat1, lon1 = waypoints[0]
            lat2, lon2 = waypoints[1]
            dx = (lon2 - lon1) * 111320  # rough meters per degree longitude at that latitude
            dy = (lat2 - lat1) * 110540  # rough meters per degree latitude
            heading_rad = atan2(dx, dy)

            # Decompose AUV velocity vector (through water)
            auv_vx = speed * sin(heading_rad)
            auv_vy = speed * cos(heading_rad)

            # Decompose current velocity vector
            current_vx = current_speed * sin(current_dir_rad)
            current_vy = current_speed * cos(current_dir_rad)

            # Ground velocity vector = AUV + current
            ground_vx = auv_vx + current_vx
            ground_vy = auv_vy + current_vy

            # Effective speed over ground (m/s)
            effective_speed = sqrt(ground_vx**2 + ground_vy**2)
            if effective_speed <= 0:
                raise ValueError("Effective ground speed is zero or negative due to current conditions.")

            # Energy use constants
            rho = 1025  # seawater density (kg/m^3)
            Cd = 0.6    # drag coefficient (adjust as needed)*****
            A = 0.2     # frontal area in m^2 (adjust as needed)*****
            efficiency = 0.5  # propulsion efficiency (adjust as needed)*****

            # Calculate drag force and power required (use AUV speed through water for drag)
            drag_force = 0.5 * rho * speed**2 * Cd * A
            power_kw = (drag_force * speed) / 1000 / efficiency  # kW

            # Mission duration in hours (distance over ground / effective speed)
            mission_duration = total_distance / effective_speed / 3600

            # Calculate vertical energy consumption per segment for variable depths
            g = 9.81  # gravity m/s^2
            vertical_speed = 0.1  # assumed constant vertical speed m/s, adjust as needed *****

            # Calculate buoyant force (if volume given, else zero)
            buoyant_force = rho * volume * g if volume > 0 else 0
            effective_weight = max(weight * g - buoyant_force, 0)  # Net downward force (N)

            # Calculate vertical drag coefficient, frontal area for vertical movement, adjust if known
            Cd_vert = 0.7  # example vertical drag coefficient, adjust as needed *****
            A_vert = 0.15  # frontal area vertically, adjust as needed *****

            # Calculate total vertical distance traveled (sum of abs depth changes between waypoints)
            total_vertical_distance = 0
            depths = [depth] * len(waypoints)  # assuming constant depth input, or could be extended to variable depths
            for i in range(len(depths) - 1):
                total_vertical_distance += abs(depths[i+1] - depths[i])  # zero here since constant depth

            # Since depth is constant for all waypoints here, total_vertical_distance=0, but you can extend

            # For now, vertical distance is just depth * 2 (down and back) or adjust as needed
            total_vertical_distance = depth * 2  # descend then ascend (meters)

            # Vertical drag force
            vertical_drag_force = 0.5 * rho * vertical_speed**2 * Cd_vert * A_vert

            # Total vertical force (weight + drag)
            total_vertical_force = effective_weight + vertical_drag_force

            # Vertical power (W) = force × speed
            vertical_power_watts = total_vertical_force * vertical_speed
            vertical_power_kw = vertical_power_watts / 1000  # kW

            # Vertical travel time (hours)
            vertical_duration = total_vertical_distance / vertical_speed / 3600

            # Vertical energy consumption (kWh)
            vertical_energy = vertical_power_kw * vertical_duration

            # Sum total battery usage
            battery_usage = power_kw * mission_duration + vertical_energy

            battery_remaining = battery_capacity - battery_usage
            battery_needed = abs(battery_remaining) if battery_remaining < 0 else 0

            return render_template("index.html",
                                   depth=depth,
                                   speed=speed,
                                   battery_capacity=battery_capacity,
                                   weight=weight,
                                   volume=volume,
                                   current_speed=current_speed,
                                   current_direction=current_dir_deg,
                                   waypoints=waypoints,
                                   total_distance=round(total_distance, 2),
                                   battery_usage=round(battery_usage, 2),
                                   battery_remaining=round(battery_remaining, 2),
                                   power_kw=round(power_kw, 2),
                                   vertical_power_kw=round(vertical_power_kw, 2),
                                   vertical_energy=round(vertical_energy, 2),
                                   duration=round(mission_duration, 2),
                                   battery_needed=round(battery_needed, 2),
                                   error=None)

        except Exception as e:
            return render_template("index.html", error=str(e), waypoints=[])

    return render_template("index.html", waypoints=[], error=None)


if __name__ == "__main__":
    app.run(debug=True)