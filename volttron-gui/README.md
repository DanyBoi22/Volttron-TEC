# User Guide for VOLTTRON-GUI # 

## Content ##
This folder contains:
- PyQT: Folder with python script for a mock-up version of pyqt-based ui. 
- React-App: Folder with source code for react-based ui.

## Description ## 
- React is a modern framework for UI development. It was used in the first version of Volttron-UI for easier interaction with Volttron.   
- PyQt is a Python native framework to develop UI. In theory, it is easier to maintain and to develop than React for the research purposes.
Both frameworks use HTTP to interact with the Backend Agent. Hence, the running Backend Agent is a requirement for the UI.
Because they are using HTTP protocol, it does not matter where you install the GUI. As long as the GUI has access to HTTP requests from the Backend Agent. This works well with locally installed GUI and VOLTTRON that runs in a container. 

## Installation ##
PyQt

- To install PyQt follow official guide https://pypi.org/project/PyQt6/.

React
- To install React follow official guide https://react.dev/learn/installation.
- After installation create a new React-App.
- Copy the contents of src and public subfolders aswell as start and stop scripts from React-App folder into your newly created React-App folder.

## Start ##
PyQt

Simply execute the python script from the PyQT subfolder. As already mentioned, at the moment it is a mockup and has almost zero functionality.

React

Execute the copied start-gui.sh. This will open a browser page with the gui. The gui is functional but may have a lot of bugs. It allows you to control installed agents and have basic experiment control. For further usage of React-App the complete refactoring of the source code is advised. 
