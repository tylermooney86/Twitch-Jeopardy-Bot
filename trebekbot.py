################################
#          TrebekBot
#         By: Shnerp
################################
'''A simple Jeopardy trivia bot for twitch chat'''

import os
from twitchio.ext import commands
import requests
import regex as re
import string
import random
import json
from fuzzywuzzy import fuzz
from config import onlineannouncements, emotes, failresponses, transitiontext, approvedusers, multipliers

BotName = os.environ['BOT_NICK']
BotCommand = os.environ['BOT_PREFIX']

global JeopardyQuestion
JeopardyQuestion = []

global IsJeopardy
IsJeopardy = False

global Losers
Losers = []

global IsWinner
IsWinner = False

global WinMessage 
WinMessage = ""

global messageBuffer
messageBuffer = []

# set up the bot
bot = commands.Bot(
    irc_token=os.environ['TMI_TOKEN'],
    client_id=os.environ['CLIENT_ID'],
    nick=os.environ['BOT_NICK'],
    prefix=os.environ['BOT_PREFIX'],
    initial_channels=[os.environ['CHANNEL']]
)

#########################
#    Initialize Bot
#########################
@bot.event
async def event_ready():
    ##Called once when the bot goes online.##
    print(f"{os.environ['BOT_NICK']} is online!")
    ws = bot._ws  # this is only needed to send messages within event_ready
    await ws.send_privmsg(os.environ['CHANNEL'], f"{random.choice(onlineannouncements)} {emotes[0]}")

#########################
#    Process Messages
#########################
@bot.event
async def event_message(ctx):
    ##Runs every time a message is sent in chat##
    global IsJeopardy, Losers, JeopardyQuestion, IsWinner, WinMessage

    message = ctx.content
    author = ctx.author.name

    # make sure the bot ignores itself
    if ctx.author.name.lower() == os.environ['BOT_NICK'].lower():        
        return

    ## Handle Commands ##
    await bot.handle_commands(ctx)

    if 'trebek' in message.lower():

        if IsJeopardy:
            is_question_format = re.search("^(what|whats|where|wheres|who|whos)",
            re.sub("[^A-Za-z0-9_ \t]", "" , message), flags=re.I)
        
            if is_question_format: 
                Losers.append(author)
                await ctx.channel.send(f"@{author} {random.choice(failresponses)}")
                return

        await ctx.channel.send(emotes[1])
        return
    
    if '!jeopardy' == message.lower():
        await startJeopardy(ctx, author, message)
    
    if IsJeopardy:
        await checkMessage(ctx, author, message)

    if messageBuffer:
            await ctx.channel.send(messageBuffer.pop())

#######################
#     Bot Commands
#######################                
@bot.command(name='help')
async def help(ctx):
    response = f"Welcome to Jeopardy! I'll be your host, {BotName}. {emotes[0]} Here's how it works: I will announce a category and ask a question. You will have one chance to respond in the form of a question. The first user with the correct response wins! To start a new round of Jeopardy, type '{BotCommand}'."
    await ctx.send(f'{response}')

@bot.command(name='repeat')
async def repeat(ctx):
    global IsJeopardy
    if IsJeopardy:
        question = json.loads(JeopardyQuestion)
        category = question.get("category", {}).get("title", "")
        value = question.get("value", 0)
        question_text = question.get("question", "")

        response = f"The category is '{category}' for ${value}: '{question_text}'"

    else:
        response = f"Sorry {ctx.author.name} there is not currently an active Jeopardy question."

    await ctx.send(response)

@bot.command(name='skip')
async def skip(ctx):
    global Losers, JeopardyQuestion
    global IsJeopardy
    author = ctx.author.name
    multiplier = random.choice(multipliers)
    ## check if author is allowed to skip ##
    if author not in approvedusers:
        return
    ## get prev answer before getting new question ##
    if JeopardyQuestion:
        try:
            question = json.loads(JeopardyQuestion)
            prevanswer = question.get("answer", "")
            prevanswer = re.sub("<.*?>", "", prevanswer)
            prevanswer = prevanswer.strip()
            
            prevanswer = f"The answer was: {prevanswer}"
        except:
            print("error loading question")
    else:
        prevanswer = "" 

    ## get question from api ##
    resp = requests.get('http://jservice.io/api/random')
    if not resp.ok:
            print("Failed to get question")

    question = resp.json()[0]
    category = question.get("category", {}).get("title", "")
    value = question.get("value", 0)
    answer = question.get("answer", "")
    answer = re.sub("<.*?>", "", answer)
    answer = answer.strip()
    question_text = question.get("question", "")
    
    # No value exists
    if not value:
        value = 200
        

    value = value * multiplier
    question["value"] = value

    # if the question has "seen here" in it, or if no question was sent in the first place, just get a new question
    while "seen here" in question_text or not question_text or "clue crew" in question_text:
        resp = requests.get('http://jservice.io/api/random')
        if not resp.ok:
            print("Failed to get question")
            return

        question = resp.json()[0]
        category = question.get("category", {}).get("title", "")
        value= question.get("value", 0)
        question_text = question.get("question", "")
        answer = question.get("answer", "")
        answer = re.sub("<.*?>", "", answer)
        answer = answer.strip()
        
        if not value:
            value = 200 

        value = value * multiplier
        question["value"] = value
    
    #save question for reference in global variable
    JeopardyQuestion = json.dumps(question)

    newquestion = f"The category is '{category}' for ${value}: '{question_text}' {emotes[1]}"
    response = f"{prevanswer}... {random.choice(transitiontext)} {newquestion}"

    Losers = []
    IsJeopardy = True
    
    #print statements for debugging
    print("---------------------------------")
    print(response)
    print("---------------------------------")
    print(answer)
    print("---------------------------------")
    await ctx.send(response)

@bot.command(name='shutdown')
async def shutdown(ctx):
    author = ctx.author.name
    ## check if author is allowed ##
    if author not in approvedusers:
        return

    await ctx.channel.send('/me is shutting down....')
    exit()

##############################
#      Jeopardy start
##############################
async def startJeopardy(ctx, author, message):
    global JeopardyQuestion, IsJeopardy, Losers
    multiplier = random.choice(multipliers)
    ## if question exists repeat question
    if IsJeopardy:
        question = json.loads(JeopardyQuestion)
        category = question.get("category", {}).get("title", "")
        value = question.get("value", 0)
        question_text = question.get("question", "")
        
        await ctx.channel.send(f"The category is '{category}' for ${value}: '{question_text}'")
        return
    
    #get question from api
    resp = requests.get('http://jservice.io/api/random')
    if not resp.ok:
            print("Failed to get question")
            return

    question = resp.json()[0]
    category = question.get("category", {}).get("title", "")
    answer = question.get("answer", "")
    answer = re.sub("<.*?>", "", answer)
    answer = answer.strip()
    question_text = question.get("question", "")
    
    value = question.get("value", 0)
    # No value exists
    if not value:
        value = 200 
    
    value = value * multiplier
    question["value"] = value 

    # if the question has "seen here" in it, or if no question was sent in the first place, just get a new question
    while "seen here" in question_text or not question_text:
        resp = requests.get('http://jservice.io/api/random')
        if not resp.ok:
            print("Failed to get question")
            return

        question = resp.json()[0]
        category = question.get("category", {}).get("title", "")
        question_text = question.get("question", "")
        answer = question.get("answer", "")
        answer = re.sub("<.*?>", "", answer)
        answer = answer.strip()
        
        value= question.get("value", 0) 
        if not value:
            value = 200 

        value = value * multiplier
        question["value"] = value
    
    #save question for reference in global variable
    JeopardyQuestion = json.dumps(question)

    response = f"The category is: '{category}'. For ${value}: '{question_text}' {emotes[1]}"

    #print statements for debugging
    print("---------------------------------")
    print(response)
    print("---------------------------------")
    print(answer)
    print("---------------------------------")

    IsJeopardy = True
    Losers = []

    await ctx.channel.send(response)
    return


#########################
#     Check Message
#########################
async def checkMessage(ctx, author, message):
    global JeopardyQuestion, IsJeopardy, Losers, WinMessage, IsWinner
    
    # return if author has already guessed
    if author in Losers:
        return

    ## check if the user responded with a question
    is_question_format = re.search("^(what|whats|where|wheres|who|whos)", re.sub("[^A-Za-z0-9_ \t]", "" , message), flags=re.I)

    if not is_question_format: 
        return

    # get data from question 
    question = json.loads(JeopardyQuestion)
    answer = cleanAnswer(question.get("answer", ""))
    value = question.get("value", 0)

    # format the user's user_response to get their answer
    user_response = cleanUserResponse(message)
    

    # Do a fuzzy comparison to see if the user's answer is close enough to correct
    is_correct = (fuzz.ratio(user_response, answer) > 60)
    try:
        if '(' in answer:
            if '(or' in answer:
                answer = re.sub("or", "", answer,flags=re.I)
            answer = re.sub("\(", ",", answer,flags=re.I)
            answer = re.sub("\)", ",", answer,flags=re.I)
            answer.strip()
            answer = answer.split(',')
            
            for ans in answer:
                if (fuzz.ratio(user_response, ans) > 50):
                    is_correct = True
    except:
        print("failed on or check")
    
    # winner winner chicken dinner
    if is_correct == True:
        Losers = []
        IsJeopardy = False

        print("---------------------------------")
        print(f"winner: {author} response: {message} answer: {answer} value: {value}")
        print("---------------------------------")

        response = f"!addpoints {author} {value} Correct! Congratulations {author}! You have won ${value} with your response: '{message}'! The judges were looking for '{answer}' {emotes[2]}"
        
        IsWinner = True
        WinMessage = response
        messageBuffer.append(response)
        return
    
    # fail fish
    else:
        Losers.append(author)
        messageBuffer.append(f"Sorry {author}, {random.choice(failresponses)} {emotes[3]}")
        return

def cleanAnswer(answer):
    answer = re.sub("<.*?>", "", answer)
    answer = answer.strip()
    answer = re.sub("[^A-Za-z0-9_ \t]", "", answer)
    answer = answer.strip()
    answer = re.sub("^(the|an)", "", answer, flags=re.I)
    answer = answer.strip()
    answer = answer.lower()
    return answer

def cleanUserResponse(message):
    # replace & with and
    user_response = re.sub("\s+(&)\s+", " and ", message)
    # remove all punctuation
    user_response = re.sub("[^A-Za-z0-9_ \t]", "", user_response)
    # remove all question elements
    user_response = re.sub("^(what |whats |where |wheres |who |whos )", "", user_response, flags=re.I)
    user_response = user_response.strip()
    user_response = re.sub("^(is |are |was |were )", "", user_response, flags=re.I)
    user_response = user_response.strip()
    user_response = re.sub("^(the |a |an )", "", user_response, flags=re.I)
    user_response = user_response.strip()
    user_response = re.sub("\?+$", "", user_response)
    user_response = user_response.strip()
    user_response = user_response.lower()
    return user_response

## Main ##
if __name__ == "__main__":
    bot.run()
