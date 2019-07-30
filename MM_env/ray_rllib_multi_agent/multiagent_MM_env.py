# https://github.com/ray-project/ray/blob/master/python/ray/rllib/examples/multiagent_cartpole.py

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
"""Simple example of setting up a multi-agent policy mapping.
Control the number of agents and policies via --num-agents and --num-policies.
This works with hundreds of agents and policies, but note that initializing
many TF policies will take some time.
Also, TF evals might slow down with large numbers of policies. To debug TF
execution, set the TF_TIMELINE_DIR environment variable.
"""

import argparse
import gym
import random

import ray
from ray import tune
from ray.rllib.models import Model, ModelCatalog
from ray.rllib.tests.test_multi_agent_env import MultiCartpole
from ray.tune.registry import register_env
from ray.rllib.utils import try_import_tf



import sys

if "../" not in sys.path:
    sys.path.append("../")

#from exchg.x.y import z
from exchg.exchg import Exchg



tf = try_import_tf()

parser = argparse.ArgumentParser()

parser.add_argument("--num-agents", type=int, default=4)
parser.add_argument("--num-policies", type=int, default=2)
parser.add_argument("--num-iters", type=int, default=20)
parser.add_argument("--simple", action="store_true")

class CustomModel1(Model):
    def _build_layers_v2(self, input_dict, num_outputs, options):
        # Example of (optional) weight sharing between two different policies.
        # Here, we share the variables defined in the 'shared' variable scope
        # by entering it explicitly with tf.AUTO_REUSE. This creates the
        # variables for the 'fc1' layer in a global scope called 'shared'
        # outside of the policy's normal variable scope.
        with tf.variable_scope(tf.VariableScope(tf.AUTO_REUSE, "shared"),
                               reuse=tf.AUTO_REUSE,
                               auxiliary_name_scope=False):
            last_layer = tf.layers.dense(input_dict["obs"], 64, activation=tf.nn.relu, name="fc1")
        last_layer = tf.layers.dense(last_layer, 64, activation=tf.nn.relu, name="fc2")
        #output = tf.layers.dense(last_layer, num_outputs, activation=None, name="fc_out")



        # ********** TESTING **********
        num_outputs = 1

        type_side_layer = tf.layers.dense(last_layer, num_outputs * 4, activation=tf.nn.relu, name="fc2")
        #type_side = tf.layers.dense(type_side_layer, num_outputs, activation=tf.nn.softmax, name="type_side")
        # use softmax for probabilities of each of the 4 outputs, all 4 probs summed to 1
        # select max prob

        mu_size = tf.layers.dense(last_layer, num_outputs, activation=tf.nn.tanh, name="mu_size")
        sigma_size = tf.layers.dense(last_layer, num_outputs, activation=tf.nn.softplus, name="sigma_size")

        mu_price = tf.layers.dense(last_layer, num_outputs, activation=tf.nn.tanh, name="mu_price")
        sigma_price = tf.layers.dense(last_layer, num_outputs, activation=tf.nn.softplus, name="sigma_price")

        norm_dist_size = tf.distributions.Normal(loc=mu_size, scale=sigma_size)
        size = tf.squeeze(norm_dist_size.sample(1), axis=0) # choosing size

        norm_dist_price = tf.distributions.Normal(loc=mu_price, scale=sigma_price)
        price = tf.squeeze(norm_dist_price.sample(1), axis=0) # choosing price



        output = {'type_side': type_side,'size': size,'price': price}

        return output, last_layer
        # ********** TESTING **********

        #return output, last_layer



class CustomModel2(Model):
    def _build_layers_v2(self, input_dict, num_outputs, options):
        # Weights shared with CustomModel1
        with tf.variable_scope(tf.VariableScope(tf.AUTO_REUSE, "shared"),
                               reuse=tf.AUTO_REUSE,
                               auxiliary_name_scope=False):
            last_layer = tf.layers.dense(input_dict["obs"], 64, activation=tf.nn.relu, name="fc1")
        last_layer = tf.layers.dense(last_layer, 64, activation=tf.nn.relu, name="fc2")
        output = tf.layers.dense(last_layer, num_outputs, activation=None, name="fc_out")
        return output, last_layer

if __name__ == "__main__":
    args = parser.parse_args()
    ray.init()

    num_of_traders = 4
    tape_display_length = 100
    tick_size = 1
    init_cash = 10000
    max_step = 100
    # Simple environment with `num_agents` independent cartpole entities
    #register_env("multi_cartpole", lambda _: MultiCartpole(args.num_agents))
    register_env("MM_env", lambda _: Exchg(args.num_agents, init_cash, tape_display_length, max_step))
    ModelCatalog.register_custom_model("model1", CustomModel1)
    #ModelCatalog.register_custom_model("model2", CustomModel2)
    #single_env = gym.make("CartPole-v0")
    #obs_space = single_env.observation_space
    #act_space = single_env.action_space
    MM_env = Exchg(num_of_traders, init_cash, tape_display_length, max_step)
    obs_space = MM_env.observation_space
    act_space = MM_env.action_space

    # Each policy can have a different configuration (including custom model)
    def gen_policy(i):
        #config = {"model": {"custom_model": ["model1", "model2"][i % 2],},
        #          "gamma": random.choice([0.95, 0.99]),}
        config = {"model": {"custom_model": "model1"},
                  "gamma": 0.95,}
        return (None, obs_space, act_space, config)

    # Setup PPO with an ensemble of `num_policies` different policies
    policies = {"policy_{}".format(i): gen_policy(i) for i in range(args.num_policies)}
    policy_ids = list(policies.keys())

    tune.run("PPO",
             stop={"training_iteration": args.num_iters},
             #config={"env": "multi_cartpole",
             config={"env": "MM_env",
                     "log_level": "DEBUG",
                     "simple_optimizer": args.simple,
                     "num_sgd_iter": 10,
                     "multiagent": {"policies": policies,
                                    "policy_mapping_fn": tune.function(lambda agent_id: random.choice(policy_ids)),
                                   },
                    },
            )
