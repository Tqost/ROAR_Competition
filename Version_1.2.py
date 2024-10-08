"""
Competition instructions:
Please do not change anything else but fill out the to-do sections.
"""

from typing import List, Tuple, Dict, Optional
import roar_py_interface
import numpy as np

# 415.45 Sec


def normalize_rad(rad: float):
    return (rad + np.pi) % (2 * np.pi) - np.pi


def filter_waypoints(
    location: np.ndarray,
    current_idx: int,
    waypoints: List[roar_py_interface.RoarPyWaypoint],
) -> int:
    def dist_to_waypoint(waypoint: roar_py_interface.RoarPyWaypoint):
        return np.linalg.norm(location[:2] - waypoint.location[:2])

    for i in range(current_idx, len(waypoints) + current_idx):
        if dist_to_waypoint(waypoints[i % len(waypoints)]) < 3:
            return i % len(waypoints)
    return current_idx


class RoarCompetitionSolution:
    def __init__(
        self,
        maneuverable_waypoints: List[roar_py_interface.RoarPyWaypoint],
        vehicle: roar_py_interface.RoarPyActor,
        camera_sensor: roar_py_interface.RoarPyCameraSensor = None,
        location_sensor: roar_py_interface.RoarPyLocationInWorldSensor = None,
        velocity_sensor: roar_py_interface.RoarPyVelocimeterSensor = None,
        rpy_sensor: roar_py_interface.RoarPyRollPitchYawSensor = None,
        occupancy_map_sensor: roar_py_interface.RoarPyOccupancyMapSensor = None,
        collision_sensor: roar_py_interface.RoarPyCollisionSensor = None,
    ) -> None:
        self.maneuverable_waypoints = maneuverable_waypoints
        self.vehicle = vehicle
        self.camera_sensor = camera_sensor
        self.location_sensor = location_sensor
        self.velocity_sensor = velocity_sensor
        self.rpy_sensor = rpy_sensor
        self.occupancy_map_sensor = occupancy_map_sensor
        self.collision_sensor = collision_sensor
        self.prev_delta_heading = 0
        self.prev_brake_heading = 0

    async def initialize(self) -> None:
        # TODO: You can do some initial computation here if you want to.
        # For example, you can compute the path to the first waypoint.

        # Receive location, rotation and velocity data

        vehicle_location = self.location_sensor.get_last_gym_observation()
        vehicle_rotation = self.rpy_sensor.get_last_gym_observation()
        vehicle_velocity = self.velocity_sensor.get_last_gym_observation()

        self.current_waypoint_idx = 10
        self.current_waypoint_idx = filter_waypoints(
            vehicle_location, self.current_waypoint_idx, self.maneuverable_waypoints
        )

    async def step(self) -> None:
        """
        This function is called every world step.
        Note: You should not call receive_observation() on any sensor here, instead use get_last_observation() to get the last received observation.
        You can do whatever you want here, including apply_action() to the vehicle.
        """
        # TODO: Implement your solution here.

        # Receive location, rotation and velocity data
        vehicle_location = self.location_sensor.get_last_gym_observation()
        vehicle_rotation = self.rpy_sensor.get_last_gym_observation()
        vehicle_velocity = self.velocity_sensor.get_last_gym_observation()
        vehicle_velocity_norm = np.linalg.norm(vehicle_velocity)

        # Find the waypoint closest to the vehicle
        self.current_waypoint_idx = filter_waypoints(
            vehicle_location, self.current_waypoint_idx, self.maneuverable_waypoints
        )
        # We use the 3rd waypoint ahead of the current waypoint as the target waypoint
        waypoint_to_follow = self.maneuverable_waypoints[
            (self.current_waypoint_idx + int(vehicle_velocity_norm / 5 + 1))
            % len(self.maneuverable_waypoints)
        ]
        vector_to_waypoint = (waypoint_to_follow.location - vehicle_location)[:2]
        heading_to_waypoint = np.arctan2(vector_to_waypoint[1], vector_to_waypoint[0])
        delta_heading = normalize_rad(heading_to_waypoint - vehicle_rotation[2])

        leading_waypoint = self.maneuverable_waypoints[
            (self.current_waypoint_idx + int(vehicle_velocity_norm / 2.5 + 2))
            % len(self.maneuverable_waypoints)
        ]
        waypoint_vector = (leading_waypoint.location - vehicle_location)[:2]
        leading_heading_to_waypoint = np.arctan2(waypoint_vector[1], waypoint_vector[0])
        leading_delta_heading = normalize_rad(
            leading_heading_to_waypoint - vehicle_rotation[2]
        )

        brake_waypoint = self.maneuverable_waypoints[
            (self.current_waypoint_idx + int(vehicle_velocity_norm / 1 + 2))
            % len(self.maneuverable_waypoints)
        ]
        brake_vector = (brake_waypoint.location - vehicle_location)[:2]
        brake_heading_to_waypoint = np.arctan2(brake_vector[1], brake_vector[0])
        brake_delta_heading = normalize_rad(
            brake_heading_to_waypoint - vehicle_rotation[2]
        )

        print(vehicle_velocity_norm)
        print(delta_heading)
        print(brake_delta_heading)
        # Proportional controller to steer the vehicle towards the target waypoint

        steer_control = (
            (
                (
                    (-(1) * (delta_heading + leading_delta_heading * 0.5) / 1.5)
                    + (2)
                    * (
                        self.prev_delta_heading
                        - (delta_heading + leading_delta_heading * 0.5) / 1.5
                    )
                )
            )
            if vehicle_velocity_norm > 1e-2
            else -np.sign(delta_heading)
        )
        print(steer_control)
        steer_control = np.clip(steer_control, -1.0, 1.0)

        # Proportional controller to control the vehicle's speed towards 40 m/s
        throttle_control = 1 * (
            80
            - (abs(delta_heading * vehicle_velocity_norm) / 3)
            - (
                2
                * vehicle_velocity_norm
                * abs(brake_delta_heading * np.sqrt(vehicle_velocity_norm))
            )
        )
        self.prev_brake_heading = brake_delta_heading
        self.prev_delta_heading = delta_heading
        control = {
            "throttle": np.clip(throttle_control, 0.0, 1.0),
            "steer": steer_control,
            "brake": np.clip(-throttle_control, 0.0, 1.0),
            "hand_brake": 0.0,
            "reverse": 0,
            "target_gear": int(vehicle_velocity_norm / 15),
        }
        await self.vehicle.apply_action(control)
        return control
