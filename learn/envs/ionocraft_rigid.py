import numpy as np
import torch
import torch.optim as optim
import math
import gym
from gym import spaces, logger
from gym.utils import seeding
from .rigidbody import RigidEnv


class IonocraftRigidEnv(RigidEnv):
    def __init__(self, dt=.001, m=.035, L=.065, Ixx=2.3951e-5, Iyy=2.3951e-5, Izz=3.2347e-5, x_noise=.0001, u_noise=0):
        super(CrazyflieRigidEnv, self).__init__(dt=dt)

        # Setup the parameters
        self.m = m
        self.L = L
        self.Ixx = Ixx
        self.Iyy = Iyy
        self.Izz = Izz
        self.g = 9.81

        # Define equilibrium input for quadrotor around hover
        # This is not the case for PWM inputs
        self.u_e = np.array([m * self.g, 0, 0, 0])
        # Four PWM inputs around hover, extracted from mean of clean_hover_data.csv
        # self.u_e = np.array([42646, 40844, 47351, 40116])

        # Angle at which to fail the episode
        self.theta_threshold_radians = 12 * 2 * math.pi / 360

        self.action_space = spaces.Box(low=np.array([0, 0, 0, 0]),
                                       high=np.array([65535, 65535, 65535, 65535]),
                                       dtype=np.int32)

    def get_obs(self):
        return np.array(self.state[6:])

    def set_state(self, x):
        self.state = x

    def get_reward(self, next_ob, action):
        # Going to make the reward -c(x) where x is the attitude based cost
        assert isinstance(next_ob, np.ndarray)
        assert isinstance(action, np.ndarray)
        assert next_ob.ndim in (1, 2)

        was1d = next_ob.ndim == 1
        if was1d:
            next_ob = np.expand_dims(next_ob, 0)
            action = np.expand_dims(action, 0)

        assert next_ob.ndim == 2
        cost_pr = np.power(next_ob[:, 0], 2) + np.power(next_ob[:, 1], 2)
        cost_rates = np.power(next_ob[:, 3], 2) + np.power(next_ob[:, 4], 2) + np.power(next_ob[:, 5], 2)
        lambda_omega = .0000
        cost = cost_pr + lambda_omega * cost_rates
        return -cost

    def get_reward_torch(self, next_ob, action):
        assert torch.is_tensor(next_ob)
        assert torch.is_tensor(action)
        assert next_ob.dim() in (1, 2)

        was1d = len(next_ob.shape) == 1
        if was1d:
            next_ob = next_ob.unsqueeze(0)
            action = action.unsqueeze(0)

        cost_pr = next_ob[:, 1].pow(2) + next_ob[:, 2].pow(2)
        cost_rates = next_ob[:, 3].pow(2) + next_ob[:, 4].pow(2) + next_ob[:, 5].pow(2)
        lambda_omega = .0000
        cost = cost_pr + lambda_omega * cost_rates
        return -cost

    def pwm_thrust_torque(self, PWM):
        # Takes in the a 4 dimensional PWM vector and returns a vector of
        # [Thrust, Taux, Tauy, Tauz] which is used for simulating rigid body dynam
        # u1 u2 u3 u4
        # u1 is the thrust along the zaxis in B, and u2, u3 and u4 are rolling, pitching and
        # yawing moments respectively

        raise NotImplementedError("TODO for ionocraft")

        def pwm_to_thrust(PWM):
            # returns thrust from PWM
            pwm_n = PWM / 65535.0
            thrust = .35 * pwm_n + .26 * pwm_n ** 2
            return thrust

        l = 35.527e-3 / np.sqrt(2)  # length to motors / axis of rotation for xy
        lz = 46e-3  # axis for tauz
        c = .025  # coupling coefficient for yaw torque

        # Estimates forces
        m1 = pwm_to_thrust(PWM[0])
        m2 = pwm_to_thrust(PWM[1])
        m3 = pwm_to_thrust(PWM[2])
        m4 = pwm_to_thrust(PWM[3])

        Thrust = (-m1 - m2 - m3 - m4)  # pwm_to_thrust(np.sum(PWM) / (4 * 65535.0))
        taux = l * (-m1 - m2 + m3 + m4)
        tauy = l * (m1 - m2 - m3 + m4)
        tauz = -lz * c * (-m1 + m2 - m3 + m4)
        return np.array([Thrust, taux, tauy, tauz])