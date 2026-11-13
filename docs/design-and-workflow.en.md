# Visual Office: design rationale and workflow

This document is not meant to help you build an identical office. It hands you "why it is designed this way" and "how it was made", so your AI can build a version of your own that fits your team, your tools and your taste.

Suggested use: give the whole document to your AI (for example Claude Code), then tell it which AIs you have, what each one does, and what art style you like. Section 8 has an opening message you can paste directly.

---

## 1. What this is

A web page showing a cozy little office where each AI is a small animal and you are the boss. Without reading any logs, one glance tells you who is busy, who is free, who is stuck, who is looking for whom, and how many things are waiting for you.

The core idea fits in one sentence: **everything an AI does must map to a human-like action**. If you can't see it, it didn't happen.

---

## 2. Design rationale: what each situation looks like

### 1. Status table

| What the AI is really doing | What you see |
|---|---|
| Online, work going well | Typing at their desk, smiling, rosy cheeks |
| Heavy workload, near the limit | Hunched over, sweating |
| Nothing to do | Goes to the lounge: drinks, cookies, TV, lying on the sofa, reading on the rug (randomly rotated, nobody always does the same thing) |
| Offline | Empty seat with an "Out" sign |
| Out of quota | K.O. on the floor, seeing stars; the card says when it recovers |
| Task failed | Swearing ＊@∆×, pounding the desk, slumped over the desk (three variants in rotation) |
| Here, but not picking up messages | Semi-transparent with a ghost tail and a "do not disturb" sign |
| Can't reach someone | Walks to their door, knocks, question mark |
| Several sessions open at once | Semi-transparent clones behind them, labelled "×4" |
| Finished something | Cheers "Done!" at their desk, then goes to rest |
| Working | Both hands move in turn, like typing; readers and document checkers move slower, like turning pages or writing |
| Can't find someone, waiting | Paces back and forth at their door with real walking steps, never floating sideways |
| Each one's quota | A health bar over their head (like a video game character) |
| Things waiting for you | Folders on your desk, one per item |

### 2. Interactions

| What really happened | What you see |
|---|---|
| A messages B | A walks over to B with "💬 B" above their head |
| Assigning work | The coordinator walks over with a folder: "📁 To B" |
| Reporting, handing in | Walks to the coordinator with a folder: "📁 Report to" |
| The other one is in the lounge | Goes straight to the lounge, not to an empty office door |
| Talking business | The one being visited stands up; both stand face to face |
| They reply while you are still at their door | They answer from their seat; the two don't walk to each other's doors and miss each other |
| The coordinator gets mail | Walks to the mailbox to collect it |
| A sandboxed AI needs someone | A call light outside the wall turns on with "Call so-and-so", and the called one walks to the door |
| You click an animal | A card pops up where you can talk to that AI directly |

### 3. Movement must make sense (every one of these was a real mistake)

- **No floating**: movement is always walking, along walkways planned on the floor, feet alternating.
- **No walking through walls**: each office is entered and left through its exit. If an exit is too narrow, add a door that opens when someone approaches.
- **No walking through each other**: when meeting someone, stop and give way, or step around them.
- **Get off the chair first**: when getting up from a chair or sofa, step onto the floor beside it before walking; sit down only after standing still at the destination.
- **Being hidden must look real**: walking behind a partition or cabinet, the object covers the character. But cover them along the object's real shape, not with a straight line or a box.
- **Collapse somewhere sensible**: open floor big enough for the whole body, never in a gap in a wall.
- **Sitting at work must look like work**: the character sits behind the desk facing the viewer, hands on the keyboard or documents, eyes on the screen or papers. Hands hanging in the air don't look like work.
- **Everything is solid**: characters, furniture, walls, doors, chairs and glass all hide what is behind them; who is in front is decided by where they touch the floor. Speech bubbles, names and health bars are not solid and are always on top. For a character inside a glass room, draw the glass over them.
- **Don't crowd the information**: keep name plates, speech bubbles and call signs apart.

### 4. Space

- Everyone has their own office with a different theme and color, so you know at a glance whose it is.
- The boss's office is the biggest.
- Name plates are real objects drawn into the picture (door signs, desk plates), left blank; the program fills in the text.
- There is a shared lounge: sofa, TV, coffee table, coffee bar, massage chair.
- AIs that can't go online or touch your files are kept in a glass sandbox with their own desk, chair and rest corner.
- Project progress is shown on the rocket launch site at the bottom right: three pads hold the most recently active projects, with a fuel bar when progress has been reported and "Fueling" when it has not.

**Settle these before drawing the background, or you'll never finish patching (this is where the most time went into redoing):**
- Every workstation: the desk is between the character and the viewer, and the character sits facing the viewer (so the face is visible); the monitor is at the side of the desk and doesn't block the face; the keyboard is right in front of the chair, within reach.
- Everyone needs a work surface; nobody should have only a chair or a beanbag.
- Every office has a clear entrance, at least one and a half characters wide, with nothing in front of the door.
- The main corridor is wide enough for two characters to pass; no floor lamps, book piles or plants in the walkways.
- The floor inside must be complete, with no missing corners.
- Sofas and other seats face the viewer, with floor left in front of them.

### 5. Office Feed and Star of the Day

Often when you open the page everyone happens to be resting, even though a lot just happened. So two more things sit below the live view:

- **Nine-shot replay**: each shot is something that really happened (who looked for whom, assigned, reported, finished, got stuck, ran out of quota), labelled "N min ago". Each shot is a small camera: the same background, cropped and focused where the event took place, with the characters involved placed in it. Clicking one enlarges and re-enacts it: the character walks over and the camera pushes in from wide to close. New ones push out the oldest.
  - This is a re-enactment from the log, not a recording, all drawn by the page itself without spending any AI quota. Say so on screen.
  - Back-and-forth messages between the same two within a short time are merged into one shot, or they flood the grid quickly.
- **Star of the Day board**: ranking by appearances this week; first place gets a certificate of praise (who they are, their specialty, what they did this week, well done). Mind fairness: if you rely on only one kind of log, an AI not connected to that source can never make the board.

### 6. Honesty

- For anything without a real data source, show "no data" rather than a fake number.
- Estimated numbers must be marked "estimate".
- A manually entered number older than half a day no longer counts.

---

## 3. Architecture (very simple)

- **One web page file**: one background image, with characters, occluders, doors and bubbles layered on top in SVG.
- **One small server** (Python's built-in features are enough, nothing to install): every few seconds it collects each AI's status and turns it into one data feed for the page.
- **The page asks the server every few seconds** and decides from the data where each animal is and what it does.

Three key techniques:

1. **The walkways are a graph of junctions and links.** Each position records which junction it connects to; to move, first work out which junctions to pass through, then walk one segment at a time.
2. **Each occluder records two things**: its outline and the line where it touches the floor. If a character's feet are behind that line, draw the object over the character.
3. **Status is derived from data**; don't let the AI report "I'm happy right now" itself.

---

## 4. Where the data comes from (swap in the tools you have)

Principle: **read the logs the tools leave behind first; don't rely on the AI reporting itself**. Things you ask an AI to report are often forgotten, or reported as hard-coded numbers.

| What you want to know | How it was actually done |
|---|---|
| Who is online, who is busy | Messaging tools between AIs usually have an "online list" command; if not, check whether the program is running |
| Who messaged whom | The messaging tool's local log: read only sender, recipient, time and read status, **never the body** |
| Messages not picked up, someone unreachable | The same log: unread for more than 5 minutes means the sender goes knocking and the recipient turns into a ghost |
| Assigning, handing in | Look at message direction (sent by the coordinator = assigning; sent to the coordinator = reporting); for AIs not on the messaging tool, watch their "input/output" folders for new files |
| Whether the sandboxed AI is busy | Whether its work log changed in the last two minutes (only the timestamp, not the contents) |
| Quota | The tool's own usage command; leave it blank if it can't be found |
| Things waiting for you | The number of sessions in the messaging tool whose status is "waiting for the user's answer" |
| Click an animal to talk | Each AI's command-line tool; the server calls it once on your behalf and shows the reply on the card |

Privacy reminder: read only "who, when, read or not", never the message body; keep confidential material out of this system.

---

## 5. How the art was made

1. **Show the AI reference images first** and settle on a style (here: detailed pixel art, a little house seen from above at an angle).
2. **Write the spec before drawing the background**: turn the checklist in section 2, point 4 (workstations, entrances, corridors) into a written spec for the drawing AI. One complete office, no characters, no text, name plates left blank.
3. **Draw characters as character sheets**: one animal per image, plain green background, a dozen or so poses in a grid (angry, slumped, K.O., knocking, lying down, drinking, eating cookies, reading on the floor...).
4. **The program removes the background and cuts the sheet automatically**: remove the green, cut it cell by cell, and save the result so it doesn't need cutting again next time.
5. **When a pose is missing, draw it with the existing character sheet attached as reference**, asking only for a pose change. If you give only a text description, the character comes out looking different.
6. **Sitting at the desk**: draw "upper body only, hands reaching down to the right onto the desk". The anchor point is the hands, which you line up on the keyboard or papers. The legs are hidden by the desk anyway, so don't draw them.
7. **Walking needs two frames**: one "stride" (one foot forward, one back) and one "feet together" (both feet under the body, one slightly lifted). Don't ask for "left foot forward / right foot forward": from a front-angled view both feet look the same and you get two identical images. Don't mirror the legs in code to fake a second frame either; the legs come out disconnected.
8. **To change only a small part of an image** (for example the desk direction in one room): crop that part, ask for the change on it alone with the outer edges unchanged, and paste it back in place. If you ask it to change the whole image, other areas drift too.
9. **Draw small things that are hard to place on their own**: a single chair, a folder and similar small objects are generated separately with the background removed, then positioned by the program.

**Have two or more AIs that can draw, and know how many separate quotas each has.** What actually happened: one's command-line tool ran out of quota for two days, and the other was blocked after drawing thirty images in a day; in the end the work got done through the first one's desktop app (a different quota from its command-line tool), with the user pasting the prompts and sending the images back.

## 6. How to check (the most important section)

The AI writing the code can't see the screen, and easily says "done" right after editing. Require it to:

- **Force every state onto the screen, take a screenshot and zoom in** before reporting it done.
- Keep "confirmed the program's logic" and "saw it on screen" apart; they are not the same.
- It only sees still frames, so you have to look yourself to judge whether the animation is right.
- Build a "track overlay" check mode: draw walkways, standing spots and occluder areas over the background, so you can see at a glance whether a route goes through a wall.
- Build a "demo mode": cycle through every state automatically so you can see them all at once.
- Every report states clearly: what was done, what was looked at, and **what was not done or not verified**.
- Changing the background is a big job: every seat, walkway, entrance, occluder and rest spot has to be measured again. Building a "measuring page with a coordinate grid" first saves a lot of time.
- Always reload the page after a change to make sure nothing broke. Changing a single line can stop the whole page from opening.

---

## 7. How to work with AIs (more important than the tech)

These rules were worked out in practice; tell your AI at the start:

1. **Keep going until it's done and done well**, unless you say stop. If one path doesn't work (an AI can't do it, can't be reached, ran out of quota), switch to the next; stop and tell you only after trying everything, and suggest alternatives.
2. **Save your time**: bundle several files into one download; give you everything to paste in one go; for something you have to repeat, do one first, get it approved, then do the rest.
3. **Always ask you questions with options**, never make you type an answer. If you send something else without answering, ask again after handling it.
4. **Don't guess, test**: whether a tool works, actually run it and see what it returns.
5. **Keep track of how each AI performs**: how easy it is to work with, how reliable its results are, in a shared table; check the table before assigning work.
6. **Always ask you before spending money, publishing anything, or deleting anything.**

## 8. How to start

Give this document to your AI and say:

> I want to build a visual office. Please follow the design rationale in this document, and don't copy someone else's picture.
> My AI team is: (list each AI's name, what it does, and what tool it runs on).
> I'm the boss and would like to be drawn as: (an animal or a look).
> The art style I like: (attach reference images or describe it).
> Please ask me about anything unclear first, then offer two art styles for me to choose from. After each state is done, take a screenshot and look at it before telling me.

Suggested order:

1. Settle the characters and the floor plan first, draw the background, and continue once you approve.
2. Draw the character sheets and hook up background removal and cutting.
3. Build the status table (the first table in section 2) and use fake data to put every state on screen for you. Get the seats right first: hands must rest on the things on the desk.
4. Build walkways, exits, giving way and occlusion.
5. Connect real data (section 4).
6. Build the interactions (the second table in section 2).
7. Build the replay and Star of the Day.
8. If needed: viewing on a phone, and a password-protected remote snapshot.

---

## 9. Optional features

- **Live view on your phone**: connect your phone back to the home computer with a private network tool, so only your devices can reach it.
- **Viewing on another computer**: upload a read-only snapshot on a timer to a password-protected static site. Strip work content and conversations from the snapshot; keep only who is online and who is busy.
  - Note: such hosting services usually meter usage. Uploading after every small change, plus too-frequent automatic uploads, can use up the whole account's quota in a day (and then other sites can't be updated either). Find out how it is billed first, finish your fixes and upload once, and automatic uploads once an hour are enough. If viewing on your phone is enough, you can skip this.
- **Start automatically at boot**: have the small server start with the computer and restart itself if it stops, rather than hanging it under one AI session (when the session closes, it goes with it). On a Mac, background services may not have permission to read the Documents folder; starting it from Terminal works.
- **Home screen icon on your phone**: make it a web page that can be added to the home screen.
- **Zoom in and out**.

---

## Appendix: about the reference implementation

This project itself is a reference implementation you can open right away. For how to start it and connect your own AIs, see the project's [README](../README.en.md).
