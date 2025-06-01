#  Index Based Log Manager
Modern applications generate vast amounts of logs essential for monitoring, debugging, and auditing.
However, as log volume increases, so do the storage costs and the complexity of retrieval. 

**Index Based Log Manager** is a project that helps to solve this problem through the following way.


##
## 🛠️ What does this project actually do? 
1. **Takes raw log files as input**.

2. **Splits logs into time-based chunks** (e.g., by second or minute).

3. **Generates a JSON index file for each chunk**, storing metadata like timestamp, log level (INFO, ERROR, etc.), and line numbers.

4. **Compresses** both the chunks and their respective index files to optimize storage.

5. **Enables fast retrieval** by decompressing only the relevant chunk based on the user’s timestamp query — avoiding full decompression.

6. **Filters logs within a chunk by log level** using the pre-built index — enabling smart and efficient access.




##
## 📁Files include:

1. **log_splitter.py**        - contains the actual logic to chunk, compress, decompress and search logs

2. **app.py**                  - flask app

3. **templates-> index.html**  - frontend

4. **Hadoop_2k (1)**           - sample log data



##
## ⚙️How to use?
### 1. UI       
    python app.py
### 2. VS Code Terminal
    python log_splitter.py


##
## UI preview:
# ![Screenshot (104)](https://github.com/user-attachments/assets/ce7ff9eb-778f-4040-9daf-c91d6969279c)


    
