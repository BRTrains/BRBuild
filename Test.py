from Builder import Builder

# A simple test to run the build process without a project file to test basic output
if __name__ == "__main__":
    builder = Builder()
    builder.build("TestProject", "TestFolder")