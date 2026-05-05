import random

secret = random.randint(1, 10)

guess = 0

print(secret)
while guess != secret:
    guess = int(input("Enter Guess: "))
    if guess == secret:
        print("Guessed it, done!")
        break