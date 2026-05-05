import csv
import os
from datetime import date

FILENAME = "expenses.csv"
FIELDNAMES = ["date", "category", "description", "amount"]


# Step 3: Load expenses from the CSV file
def load_expenses():
    expenses = []
    if os.path.exists(FILENAME):
        with open(FILENAME, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["amount"] = float(row["amount"])  # convert back from string
                expenses.append(row)
    return expenses


# Step 4: Save all expenses to the CSV file
def save_expenses(expenses):
    with open(FILENAME, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(expenses)


# Step 5: Add a new expense
def add_expense(expenses):
    category = input("Category (e.g. Food, Transport, Bills): ").strip()
    description = input("Description: ").strip()

    while True:
        try:
            amount = float(input("Amount: "))
            break
        except ValueError:
            print("Please enter a valid number.")

    expense = {
        "date": date.today().isoformat(),  # e.g. "2024-03-15"
        "category": category,
        "description": description,
        "amount": amount,
    }

    expenses.append(expense)
    save_expenses(expenses)
    print(f"  Expense of ${amount:.2f} added under '{category}'.")


# Step 6: View all expenses
def view_expenses(expenses):
    if not expenses:
        print("  No expenses recorded yet.")
        return

    print(f"\n  {'#':<4} {'Date':<12} {'Category':<15} {'Description':<25} {'Amount':>8}")
    print("  " + "-" * 68)

    for i, e in enumerate(expenses, start=1):
        print(f"  {i:<4} {e['date']:<12} {e['category']:<15} {e['description']:<25} ${e['amount']:>7.2f}")

    print()


# Step 7: Show a summary grouped by category
def view_summary(expenses):
    if not expenses:
        print("  No expenses to summarize.")
        return

    totals = {}
    for e in expenses:
        totals[e["category"]] = totals.get(e["category"], 0) + e["amount"]

    print("\n  --- Summary by Category ---")
    for category, total in sorted(totals.items()):
        print(f"  {category:<20} ${total:.2f}")

    print("  " + "-" * 30)
    print(f"  {'Grand Total':<20} ${sum(totals.values()):.2f}\n")


# Step 8: Main menu loop
def main_menu(expenses):
    while True:
        print("\n  === Expense Tracker ===")
        print("  1. Add Expense")
        print("  2. View All Expenses")
        print("  3. View Summary")
        print("  4. Quit")

        choice = input("\n  Choose an option (1-4): ").strip()

        if choice == "1":
            add_expense(expenses)
        elif choice == "2":
            view_expenses(expenses)
        elif choice == "3":
            view_summary(expenses)
        elif choice == "4":
            print("  Goodbye!")
            break
        else:
            print("  Invalid choice. Please enter 1, 2, 3, or 4.")


# Step 9: Entry point
if __name__ == "__main__":
    expenses = load_expenses()  # load first, then show menu
    main_menu(expenses)