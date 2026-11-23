from pokerkit import HandHistory

with open("hand.phh") as f:
    hh = HandHistory.loads(f.read())

# do data analysis here