from input_handler import get_input
from calculator import calculate

def main():
    a, b, op = get_input()
    result = calculate(a, b, op)
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
