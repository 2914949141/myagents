import os

from agent_hemo.agent_loop import AgentLoop
from agent_hemo.settings import PROJECT_ROOT

def main():
    os.chdir(PROJECT_ROOT)
    agent_loop = AgentLoop()
    agent_loop.loop()    

if __name__ == "__main__":
    main()
