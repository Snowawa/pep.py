from constants import exceptions
from constants import clientPackets
from objects import glob
from objects import fokabot
from constants import serverPackets
from helpers import discordBotHelper
from helpers import logHelper as log
from helpers import userHelper
import time

def handle(userToken, packetData):
	"""
	Event called when someone sends a public message

	userToken -- request user token
	packetData -- request data bytes
	"""

	try:
		# Get userToken data
		userID = userToken.userID
		username = userToken.username
		
		# Make sure the user is not in restricted mode
		if userToken.restricted == True:
			raise exceptions.userRestrictedException

		# Public chat packet
		packetData = clientPackets.sendPublicMessage(packetData)

		# Receivers
		who = []

		# Make sure the user is not silenced
		if userToken.isSilenced() == True:
			raise exceptions.userSilencedException

		# Check message length
		packetData["message"] = packetData["message"][:2048]+"..." if len(packetData["message"]) > 2048 else packetData["message"]

		# Get receivers list
		# Check #spectator
		if packetData["to"] == "#spectator":
			# Spectator channel
			# Send this packet to every spectator and host
			if userToken.spectating == 0:
				# We have sent to send a message to our #spectator channel
				targetToken = userToken
				who = targetToken.spectators[:]
				# No need to remove us because we are the host so we are not in spectators list
			else:
				# We have sent a message to someone else's #spectator
				targetToken = glob.tokens.getTokenFromUserID(userToken.spectating)
				who = targetToken.spectators[:]

				# Remove us
				if userID in who:
					who.remove(userID)

				# Add host
				who.append(targetToken.userID)
		elif packetData["to"] == "#multiplayer":
			# Multiplayer Channel
			# Get match ID and match object
			matchID = userToken.matchID

			# Make sure we are in a match
			if matchID == -1:
				return

			# Make sure the match exists
			if matchID not in glob.matches.matches:
				return

			# The match exists, get object
			match = glob.matches.matches[matchID]

			# Create targets list
			who = []
			for i in range(0,16):
				uid = match.slots[i]["userID"]
				if uid > -1 and uid != userID:
					who.append(uid)
		else:
			# Standard channel
			# Make sure the channel exists
			if packetData["to"] not in glob.channels.channels:
				raise exceptions.channelUnknownException

			# Make sure the channel is not in moderated mode
			if glob.channels.channels[packetData["to"]].moderated == True and userToken.admin == False:
				raise exceptions.channelModeratedException

			# Make sure we have write permissions
			if glob.channels.channels[packetData["to"]].publicWrite == False and userToken.admin == False:
				raise exceptions.channelNoPermissionsException

			# Send this packet to everyone in that channel except us
			who = glob.channels.channels[packetData["to"]].getConnectedUsers()[:]
			if userID in who:
				who.remove(userID)

		# We have receivers
		# Send packet to required users
		glob.tokens.multipleEnqueue(serverPackets.sendMessage(username, packetData["to"], packetData["message"]), who, False)

		# Fokabot command check
		fokaMessage = fokabot.fokabotResponse(username, packetData["to"], packetData["message"])
		if fokaMessage != False:
			who.append(userID)
			glob.tokens.multipleEnqueue(serverPackets.sendMessage("FokaBot", packetData["to"], fokaMessage), who, False)
			log.chat("FokaBot @ {}: {}".format(packetData["to"], str(fokaMessage.encode("UTF-8"))))

		# Spam protection
		userToken.spamProtection()

		# Console and file log
		log.chat("{fro} @ {to}: {message}".format(fro=username, to=packetData["to"], message=str(packetData["message"].encode("utf-8"))))

		# Discord log
		discordBotHelper.sendChatlog("**{fro} @ {to}:** {message}".format(fro=username, to=packetData["to"], message=str(packetData["message"].encode("utf-8"))[2:-1]))
	except exceptions.userSilencedException:
		userToken.enqueue(serverPackets.silenceEndTime(userToken.getSilenceSecondsLeft()))
		log.warning("{} tried to send a message during silence".format(username))
	except exceptions.channelModeratedException:
		log.warning("{} tried to send a message to a channel that is in moderated mode ({})".format(username, packetData["to"]))
	except exceptions.channelUnknownException:
		log.warning("{} tried to send a message to an unknown channel ({})".format(username, packetData["to"]))
	except exceptions.channelNoPermissionsException:
		log.warning("{} tried to send a message to channel {}, but they have no write permissions".format(username, packetData["to"]))
	except exceptions.messageTooLongException:
		# Message > 256 silence
		userToken.silence(2*3600, "Sending messages longer than 256 characters")
	except exceptions.userRestrictedException:
		pass
