# Video/Image Labeling Tool

This is a web-based tool for labeling sequential images, built with Streamlit and containerized with Docker.

### Prerequisites

* [Docker](https://docs.docker.com/engine/install/)
* [Docker Compose](https://docs.docker.com/compose/install/)

### How to Use

#### 1. Prepare the Project

Clone or download all project files (`Makefile`, `docker-compose.yml`, `labeling_app.py`, `requirements.txt`) into a single directory.

#### 2. Run the Application

Open a terminal, navigate to the project directory, and run the following command. You need to specify the path to the directory containing your image folders.

```
make run DATA_DIR=/path/to/your/data_directory
```

**Examples:**

* **macOS / Linux:**
    ```
    make run DATA_DIR=/Users/myname/Pictures/datasets
    ```

* **Windows:**
    ```
    make run DATA_DIR=D:\MyProjects\image_data
    ```

This command will:

1.  Build the Docker image if it doesn't exist.
2.  Start the application in the background.
3.  Mount your specified `DATA_DIR` to the `/data` directory inside the container. **No files will be copied.**

#### 3. Access the Application

Open your web browser and go to:
**[http://localhost:38501](http://localhost:38501)**

#### 4. Using the Tool

1.  In the sidebar, select the target folder containing your images from the dropdown menu.
2.  Click the **"Start Labeling with This Folder"** button.
3.  Use the main interface to label your images. Your progress is saved automatically.

#### 5. Stop the Application

To stop the tool, run the following command in your terminal:

```
make down
```

This will gracefully shut down and remove the container. Your work state will be preserved in the `.session_state.pkl` file for the next session.

### Key Features

* **Direct Folder Access**: Label images directly from any folder on your PC without copying or moving data.
* **Session Persistence**: Automatically saves and restores your work, including the last viewed image, all labels, and settings.
* **Configurable Labels**: Edit labels manually in the text area or upload a `.txt` file for quick setup.
* **Flexible CSV Export**: Export labeling results as a CSV file. You can choose whether to include unlabeled images.
