#!/usr/bin/env python
#
# License: BSD
#   https://raw.githubusercontent.com/stonier/py_trees/devel/LICENSE
#
##############################################################################
# Documentation
##############################################################################

"""
About
^^^^^

A few new items arriving in tantalising bowls of flying spaghetti here:

* A gui for manually triggering events
* A gui (same one) for visualising the led strip status
* A lower priority work branch triggered from the gui
* A first action client behaviour
* A kind of pre-emption, via behaviour tree decision logic

Tree
^^^^

.. graphviz:: dot/tutorial-five.dot

.. literalinclude:: ../py_trees_ros/tutorials/five.py
   :language: python
   :linenos:
   :lines: 121-179
   :caption: py_trees_ros/tutorials/five.py#create_root

**Guards**

.. graphviz:: dot/tutorial-five-guard.dot

The entire scan branch is protected by a :term:`guard` (note that the blackbox
in the above diagram is exactly that, a black box representing the lower
part of the tree). Once the scan event is received, this branch gets to work
until it either finishes, or is pre-empted by the higher priority low battery
branch.

**A Kind of Preemption**

.. graphviz:: dot/tutorial-five-preempt.dot

The second part of the tree enables a kind of pre-emption on the scanning action.
If a new request comes in, it will trigger the secondary scan event check, invalidating
whatever scanning action was currently running. This will clear the led command and
cancel the rotate action. On the next tick, the scan event check will fail (it was
consumed on the last tick) and the scanning will restart.

.. note::
    This is not true pre-emption since it cancels the rotate action and restarts it. It is
    however, exactly the pattern that is required in many instances. For true pre-emption
    you could bundle both scan check and rotation action in the same behaviour or dynamically
    insert action goals on the fly from the parent class.

**Handling Failure**

If the rotate action should fail, then the whole branch will also fail. Subsequently
dropping the robot back to its idle state. A failure event could be generated by
simply watching either the 'Scanning' parallel or the :meth:`~py_trees.trees.BehaviourTree.tip`
of the tree and reacting to it's state change.

Behaviours
^^^^^^^^^^

Introducing the rotate action client behaviour!

.. literalinclude:: ../py_trees_ros/tutorials/five.py
   :language: python
   :linenos:
   :lines: 158-163
   :caption: py_trees_ros/tutorials/five.py#action_client_instantiation

.. literalinclude:: ../py_trees_ros/actions.py
   :language: python
   :linenos:
   :lines: 28-121
   :caption: py_trees_ros/actions.py#ActionClient

The :class:`~py_trees_ros.actions.ActionClient` is a generic template that can be used as
a drop-in for very simply monitoring the aborted/cancelled/running/success state of an
underlying controller with a pre-configured goal. See the :class:`api <py_trees_ros.actions.ActionClient>`
for details on when/how you might wish to extend this.

Running
^^^^^^^

.. code-block:: bash

    $ roslaunch py_trees_ros tutorial_five.launch --screen

**Playing with the Spaghetti**

* Press the scan button to start a scan
* Press the scan button again while mid-scanning to pre-empt
* Set battery low in reconfigure whilst mid-scanning to priority switch

.. image:: images/tutorial-five-scanning.png
"""

##############################################################################
# Imports
##############################################################################

import functools
import py_trees
import py_trees_ros
import py_trees.console as console
import py_trees_msgs.msg as py_trees_msgs
import rospy
import sys

##############################################################################
# Behaviours
##############################################################################


def create_root():
    # behaviours
    root = py_trees.composites.Parallel("Tutorial")
    topics2bb = py_trees.composites.Sequence("Topics2BB")
    scan2bb = py_trees_ros.subscribers.EventToBlackboard(
        name="Scan2BB",
        topic_name="/dashboard/scan",
        variable_name="event_scan_button"
    )
    battery2bb = py_trees_ros.battery.ToBlackboard(name="Battery2BB",
                                                   topic_name="/battery/state",
                                                   threshold=30.0
                                                   )
    priorities = py_trees.composites.Selector("Priorities")
    battery_check = py_trees.meta.success_is_failure(py_trees.composites.Selector)(name="Battery Emergency")
    is_battery_ok = py_trees.blackboard.CheckBlackboardVariable(
        name="Battery Ok?",
        variable_name='battery_low_warning',
        expected_value=False
    )
    flash_led_strip = py_trees_ros.tutorials.behaviours.FlashLedStrip(
        name="Flash Red",
        colour="red")

    scan = py_trees.composites.Sequence(name="Scan")
    is_scan_requested = py_trees.blackboard.CheckBlackboardVariable(
        name="Scan?",
        variable_name='event_scan_button',
        expected_value=True
    )
    scan_preempt = py_trees.composites.Selector(name="Preempt?")
    is_scan_requested_two = py_trees.meta.success_is_running(py_trees.blackboard.CheckBlackboardVariable)(
        name="Scan?",
        variable_name='event_scan_button',
        expected_value=True
    )
    scanning = py_trees.composites.Parallel(name="Scanning", policy=py_trees.common.ParallelPolicy.SUCCESS_ON_ONE)
    scan_rotate = py_trees_ros.actions.ActionClient(
        name="Rotate",
        action_namespace="/rotate",
        action_spec=py_trees_msgs.RotateAction,
        action_goal=py_trees_msgs.RotateGoal()
    )
    scan_flash_blue = py_trees_ros.tutorials.behaviours.FlashLedStrip(name="Flash Blue", colour="blue")
    scan_celebrate = py_trees.composites.Parallel(name="Celebrate", policy=py_trees.common.ParallelPolicy.SUCCESS_ON_ONE)
    scan_flash_green = py_trees_ros.tutorials.behaviours.FlashLedStrip(name="Flash Green", colour="green")
    scan_pause = py_trees.timers.Timer("Pause", duration=3.0)
    idle = py_trees.behaviours.Running(name="Idle")

    # tree
    root.add_children([topics2bb, priorities])
    topics2bb.add_children([scan2bb, battery2bb])
    priorities.add_children([battery_check, scan, idle])
    battery_check.add_children([is_battery_ok, flash_led_strip])
    scan.add_children([is_scan_requested, scan_preempt, scan_celebrate])
    scan_preempt.add_children([is_scan_requested_two, scanning])
    scanning.add_children([scan_rotate, scan_flash_blue])
    scan_celebrate.add_children([scan_flash_green, scan_pause])
    return root


def shutdown(behaviour_tree):
    behaviour_tree.interrupt()

##############################################################################
# Main
##############################################################################


def main():
    """
    Entry point for the demo script.
    """
    rospy.init_node("tree")
    root = create_root()
    behaviour_tree = py_trees_ros.trees.BehaviourTree(root)
    rospy.on_shutdown(functools.partial(shutdown, behaviour_tree))
    if not behaviour_tree.setup(timeout=15):
        console.logerror("failed to setup the tree, aborting.")
        sys.exit(1)
    behaviour_tree.tick_tock(500)
