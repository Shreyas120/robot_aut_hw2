from random import sample, seed
from re import A
import time
import pickle
import numpy as np

# import vrep_interface as vpi
import RobotUtil as rt
import Franka
import time

# Mujoco Imports
import mujoco as mj
from mujoco import viewer

# Seed the random object
seed(10)

# Open the simulator model from the MJCF file

os_path = "/home/shreyas/Desktop/Autonomy/hw2"
xml_filepath = os_path + "/franka_emika_panda/panda_with_hand_torque.xml"

np.random.seed(0)
deg_to_rad = np.pi/180.

#Initialize robot object
mybot = Franka.FrankArm()

# Initialize some variables related to the simulation
joint_counter = 0

# Initializing planner variables as global for access between planner and simulator
plan=[]
interpolated_plan = []
plan_length = len(plan)
inc = 1

# Add obstacle descriptions into pointsObs and axesObs
pointsObs=[]
axesObs=[]

envpoints, envaxes = rt.BlockDesc2Points(rt.rpyxyz2H([0,0.,0.],[0.1,0,1.0]),[1.3,1.4,0.1])
pointsObs.append(envpoints), axesObs.append(envaxes)

envpoints, envaxes = rt.BlockDesc2Points(rt.rpyxyz2H([0,0.,0.],[0.1,-0.65,0.475]),[1.3,0.1,0.95])
pointsObs.append(envpoints), axesObs.append(envaxes)

envpoints, envaxes = rt.BlockDesc2Points(rt.rpyxyz2H([0,0.,0.],[0.1, 0.65,0.475]),[1.3,0.1,0.95])
pointsObs.append(envpoints), axesObs.append(envaxes)

envpoints, envaxes = rt.BlockDesc2Points(rt.rpyxyz2H([0,0.,0.],[-0.5, 0, 0.475]),[0.1,1.2,0.95])
pointsObs.append(envpoints), axesObs.append(envaxes)

envpoints, envaxes = rt.BlockDesc2Points(rt.rpyxyz2H([0,0.,0.],[0.45, 0, 0.25]),[0.5,0.4,0.5])
pointsObs.append(envpoints), axesObs.append(envaxes)
	

# define start and goal
deg_to_rad = np.pi/180.

# set the initial and goal joint configurations
qInit = np.array([-np.pi/2, -np.pi/2, np.pi/2, -np.pi/2, 0, np.pi - np.pi/6, 0])
qGoal = np.array([np.pi/2, -np.pi/2, -np.pi/2, -np.pi/2, 0, np.pi - np.pi/6, 0])

# Initialize some data containers for the RRT planner
rrtVertices=[]
rrtEdges=[]

rrtVertices.append(qInit)
rrtEdges.append(0)

thresh=0.1
FoundSolution=False
SolutionInterpolated = False

# Utility function to find the index of the nearset neighbor in an array of neighbors in prevPoints
def FindNearest(prevPoints,newPoint):
	D=np.array([np.linalg.norm(np.array(point)-np.array(newPoint)) for point in prevPoints])
	return D.argmin()

# Utility function for smooth linear interpolation of RRT plan, used by the controller
def naive_interpolation(plan):

	angle_resolution = 0.01

	global interpolated_plan 
	global SolutionInterpolated
	interpolated_plan = np.empty((1,7))
	np_plan = np.array(plan)
	interpolated_plan[0] = np_plan[0]
	
	for i in range(np_plan.shape[0]-1):
		max_joint_val = np.max(np_plan[i+1] - np_plan[i])
		number_of_steps = int(np.ceil(max_joint_val/angle_resolution))
		inc = (np_plan[i+1] - np_plan[i])/number_of_steps

		for j in range(1,number_of_steps+1):
			step = np_plan[i] + j*inc
			interpolated_plan = np.append(interpolated_plan, step.reshape(1,7), axis=0)


	SolutionInterpolated = True
	print("Plan has been interpolated successfully!")



#TODO: - Create RRT to find path to a goal configuration by completing the function
# below. Use the global rrtVertices, rrtEdges, plan and FoundSolution variables in 
# your algorithm

def RRTQuery():

	global FoundSolution
	global plan
	global rrtVertices
	global rrtEdges
	
	# global mybot
	# global pointsObs
	# global axesObs
	# global thresh

	while len(rrtVertices)<3000 and not FoundSolution:

		# print(rrtVertices)
		# print(rrtEdges)

		# Fill in the algorithm here
		qRand = np.array(mybot.SampleRobotConfig())
		
		#Goal bias
		if np.random.uniform(0,1) < 0.05:
			qRand = qGoal
			print("Goal biasing")

		idNear = FindNearest(rrtVertices,qRand)
		qNear = np.array(rrtVertices[idNear])

		# RRT Connect
		while np.linalg.norm(qRand - qNear) > thresh:
			qConnect = np.array(qNear) + (thresh*(np.array(qRand)-np.array(qNear))/ np.linalg.norm(qRand-qNear))

			if not mybot.DetectCollisionEdge(qConnect, qNear, pointsObs, axesObs):
				rrtVertices.append(qConnect)
				rrtEdges.append(idNear)
				qNear = qConnect
			else:
				break
		
		qConnect = qRand

		# if np.linalg.norm(qRand - qNear) > thresh:
		# 	qConnect = np.array(qNear) + (thresh*(np.array(qRand)-np.array(qNear))/ np.linalg.norm(qRand-qNear))
		# else:
		# 	qConnect = qRand
		

		if not mybot.DetectCollisionEdge(qConnect, qNear, pointsObs, axesObs):
			rrtVertices.append(qConnect)
			rrtEdges.append(idNear)

		idNear = FindNearest(rrtVertices, qGoal)
		if np.linalg.norm(qGoal - rrtVertices[idNear]) < 0.025:
			rrtVertices.append(qGoal)
			rrtEdges.append(idNear)
			FoundSolution = True
			break

		print("Vertices", len(rrtVertices))
		
			
	### if a solution was found
	if FoundSolution:
		# Extract path
		c=-1 #Assume last added vertex is at goal 
		plan.insert(0, rrtVertices[c])
		while True:
			c=rrtEdges[c]
			print(c, len(plan))
			plan.insert(0, rrtVertices[c])
			if c==0:
				break

		# # TODO - Path shortening
		# for i in range(150):
		# 	anchorA = np.random.randint(0, len(plan)-2)
		# 	anchorB = np.random.randint(anchorA + 1, len(plan)-1)

		# 	shiftA, shiftB = np.random.uniform(0,1,(2,))
	
		# 	candidateA = (1-shiftA)*plan[anchorA] + shiftA*plan[anchorA+1]
		# 	candidateB = (1-shiftB)*plan[anchorB] + shiftB*plan[anchorB+1]

		# 	if not mybot.DetectCollisionEdge(candidateA, candidateB, pointsObs, axesObs):
		# 		while anchorB > anchorA:
		# 			plan.pop(anchorB)
		# 			anchorB = anchorB - 1

		# 		plan.insert(anchorA+1, candidateB)
		# 		plan.insert(anchorA+1, candidateA)

		for (i, q) in enumerate(plan):
			print("Plan step: ", i, "and joint: ", q)
		plan_length = len(plan)
		
		naive_interpolation(plan)

		return

	else:
		print("No solution found")



################################# YOU DO NOT NEED TO EDIT ANYTHING BELOW THIS ##############################

def position_control(model, data):

	global joint_counter
	global inc
	global plan
	global plan_length
	global interpolated_plan

	# Instantite a handle to the desired body on the robot
	body = data.body("hand")

	# Check if plan is available, if not go to the home position
	if (FoundSolution==False or SolutionInterpolated==False):
		desired_joint_positions = np.array(qInit)
	
	else:

		# If a plan is available, cycle through poses
		plan_length = interpolated_plan.shape[0]

		if np.linalg.norm(interpolated_plan[joint_counter] - data.qpos[:7]) < 0.01 and joint_counter < plan_length:
			joint_counter+=inc

		desired_joint_positions = interpolated_plan[joint_counter]

		if joint_counter==plan_length-1:
			inc = -1*abs(inc)
			joint_counter-=1
		if joint_counter==0:
			inc = 1*abs(inc)
	

	# Set the desired joint velocities
	desired_joint_velocities = np.array([0,0,0,0,0,0,0])

	# Desired gain on position error (K_p)
	Kp = np.eye(7,7)*300

	# Desired gain on velocity error (K_d)
	Kd = 50

	# Set the actuator control torques
	data.ctrl[:7] = data.qfrc_bias[:7] + Kp@(desired_joint_positions-data.qpos[:7]) + Kd*(desired_joint_velocities-data.qvel[:7])


if __name__ == "__main__":

	# Load the xml file here
	model = mj.MjModel.from_xml_path(xml_filepath)
	data = mj.MjData(model)

	# Set the simulation scene to the home configuration
	mj.mj_resetDataKeyframe(model, data, 0)

	# Set the position controller callback
	mj.set_mjcb_control(position_control)

	# Compute the RRT solution
	RRTQuery()

	# Launch the simulate viewer
	viewer.launch(model, data)