from input_parser import InputParser


def main():
    # import data

    # parse input
    shifts = InputParser.parse_input('data/shifts.csv')
    tasks = InputParser.parse_input('data/tasks.csv')
    
    # solve problem: lp class

    #dashboard



if __name__ == "__main__":
    main()