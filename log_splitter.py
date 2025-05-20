import os
import re
from datetime import datetime
import json
import gzip
import shutil
import tempfile

class LogProcessor:
    def __init__(self, input_file):
        self.input_file = input_file
        # Create necessary directories
        self.output_dir = "chunks"
        self.index_dir = "indexes"
        self.compressed_chunks_dir = "compressed_chunks"
        self.compressed_index_dir = "compressed_index"
        
        for directory in [self.output_dir, self.index_dir, 
                         self.compressed_chunks_dir, self.compressed_index_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def reset_processing(self):
        """Delete all processed and compressed files to allow reprocessing."""
        directories = [self.output_dir, self.index_dir, 
                      self.compressed_chunks_dir, self.compressed_index_dir]
        
        for directory in directories:
            if os.path.exists(directory):
                # Remove all files in the directory
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.unlink(file_path)
                        print(f"Deleted: {file_path}")
                    except Exception as e:
                        print(f"Error deleting {file_path}: {e}")
        
        print("\nAll processed files have been deleted. You can now reprocess the log file.")

    def extract_log_type(self, line):
        """Extract the log type (INFO, ERROR, WARN, etc.) from a log line."""
        match = re.search(r'\s(INFO|ERROR|WARN|DEBUG|FATAL)\s', line)
        if match:
            return match.group(1)
        return "UNKNOWN"

    def split_by_second(self):
        """Split log file into separate files based on seconds in timestamp."""
        # Check if files are already compressed
        if os.path.exists(self.compressed_chunks_dir) and os.listdir(self.compressed_chunks_dir):
            print("\nFiles are already processed and compressed!")
            print("Use the 'Reset Processing' option if you want to reprocess the log file.")
            return 0

        # Dictionary to store logs for each second
        logs_by_second = {}
        # Dictionary to store indexes for each second
        indexes_by_second = {}
        
        # Regular expression to match timestamp format
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})'
        
        with open(self.input_file, 'r', encoding='utf-8') as file:
            for line in file:
                # Try to find timestamp in the line
                match = re.search(timestamp_pattern, line)
                if match:
                    timestamp_str = match.group(1)
                    # Parse the timestamp
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    # Create key in format HH_MM_SS
                    time_key = timestamp.strftime('%H_%M_%S')
                    
                    # Add line to appropriate second bucket
                    if time_key not in logs_by_second:
                        logs_by_second[time_key] = []
                        indexes_by_second[time_key] = []
                    
                    # Get the line number within this time bucket
                    line_num = len(logs_by_second[time_key]) + 1
                    
                    # Add line to logs
                    logs_by_second[time_key].append(line.strip())  # Strip whitespace
                    
                    # Add index entry
                    log_type = self.extract_log_type(line)
                    index_entry = {
                        "line_number": line_num,
                        "log_type": log_type
                    }
                    indexes_by_second[time_key].append(index_entry)
        
        # Write each second's logs and indexes to separate files
        for time_key in logs_by_second:
            # Write log file
            log_file = os.path.join(self.output_dir, f"{time_key}.log")
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(logs_by_second[time_key]) + '\n')  # Join with newlines
            
            # Write index file
            index_file = os.path.join(self.index_dir, f"{time_key}.json")
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "total_lines": len(logs_by_second[time_key]),
                    "entries": indexes_by_second[time_key]
                }, f, indent=2)
            
            print(f"Created: {time_key}.log with {len(logs_by_second[time_key])} log entries")
            print(f"Created: {time_key}.json index file")
        
        return len(logs_by_second)

    def compress_files(self):
        """Compress all log and index files."""
        # Check if files are already compressed
        if os.path.exists(self.compressed_chunks_dir) and os.listdir(self.compressed_chunks_dir):
            print("\nFiles are already compressed!")
            print("Use the 'Reset Processing' option if you want to reprocess the log file.")
            return

        # Compress log files
        for filename in os.listdir(self.output_dir):
            if filename.endswith('.log'):
                input_path = os.path.join(self.output_dir, filename)
                output_path = os.path.join(self.compressed_chunks_dir, filename + '.gz')
                
                with open(input_path, 'rb') as f_in:
                    with gzip.open(output_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                print(f"Compressed: {filename}")

        # Compress index files
        for filename in os.listdir(self.index_dir):
            if filename.endswith('.json'):
                input_path = os.path.join(self.index_dir, filename)
                output_path = os.path.join(self.compressed_index_dir, filename + '.gz')
                
                with open(input_path, 'rb') as f_in:
                    with gzip.open(output_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                print(f"Compressed: {filename}")

    def view_logs_by_timestamp(self, timestamp, log_type=None):
        """View logs for a specific timestamp by decompressing the file temporarily.
        Optional log_type parameter to filter logs by type (INFO, ERROR, etc.)"""
        # Convert timestamp format from HH:MM:SS to HH_MM_SS
        try:
            # Parse the timestamp to validate format
            datetime.strptime(timestamp, '%H:%M:%S')
            time_key = timestamp.replace(':', '_')
        except ValueError:
            print("Invalid timestamp format. Please use HH:MM:SS format.")
            return

        # Check if compressed files exist
        compressed_log = os.path.join(self.compressed_chunks_dir, f"{time_key}.log.gz")
        compressed_index = os.path.join(self.compressed_index_dir, f"{time_key}.json.gz")
        
        if not os.path.exists(compressed_log):
            print(f"No logs found for timestamp {timestamp}")
            return

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Decompress and read the log file
                with gzip.open(compressed_log, 'rb') as f_in:
                    log_content = f_in.read().decode('utf-8').splitlines()
                
                # Decompress and read the index file
                with gzip.open(compressed_index, 'rb') as f_in:
                    index_content = json.loads(f_in.read().decode('utf-8'))
                
                # Filter logs if log_type is specified
                if log_type:
                    # Get line numbers for the specified log type
                    filtered_lines = []
                    for entry in index_content['entries']:
                        if entry['log_type'] == log_type:
                            # Line numbers are 1-based in the index
                            filtered_lines.append(log_content[entry['line_number'] - 1])
                    
                    # Update display content
                    log_content = filtered_lines
                    total_lines = len(filtered_lines)
                else:
                    total_lines = index_content['total_lines']
                
                # Display the contents
                print(f"\nLogs for timestamp {timestamp}" + 
                      (f" (filtered by {log_type})" if log_type else ""))
                print(f"Total log entries: {total_lines}")
                print("-" * 80)
                
                # Display the logs
                for line in log_content:
                    if line.strip():  # Only print non-empty lines
                        print(line.strip())
                
                print("-" * 80)
            
            except Exception as e:
                print(f"Error reading logs: {str(e)}")

    def get_original_size(self):
        """Get the size of the original input file."""
        return os.path.getsize(self.input_file)

    def get_total_compressed_size(self):
        """Calculate the total size of all compressed files."""
        total_size = 0
        
        # Add size of compressed log files
        if os.path.exists(self.compressed_chunks_dir):
            for filename in os.listdir(self.compressed_chunks_dir):
                if filename.endswith('.gz'):
                    total_size += os.path.getsize(os.path.join(self.compressed_chunks_dir, filename))
        
        # Add size of compressed index files
        if os.path.exists(self.compressed_index_dir):
            for filename in os.listdir(self.compressed_index_dir):
                if filename.endswith('.gz'):
                    total_size += os.path.getsize(os.path.join(self.compressed_index_dir, filename))
        
        return total_size

def main():
    # Use your specific log file
    input_file = "Hadoop_2k (1).log"
    processor = LogProcessor(input_file)
    
    while True:
        print("\nLog Viewer Menu:")
        print("1. Process and compress log files")
        print("2. View logs by timestamp")
        print("3. View filtered logs by timestamp and type")
        print("4. Reset Processing (Use after modifying the log file)")
        print("5. Exit")
        
        choice = input("Enter your choice (1-5): ")
        
        if choice == "1":
            print(f"\nProcessing file: {input_file}")
            print("Splitting logs by second and creating indexes...")
            num_files = processor.split_by_second()
            if num_files > 0:
                print(f"\nCreated {num_files} files in the 'chunks' directory")
                print(f"Created {num_files} index files in the 'indexes' directory")
                print("\nCompressing files...")
                processor.compress_files()
                print("\nCompression complete!")
        
        elif choice == "2":
            timestamp = input("\nEnter timestamp to view logs (HH:MM:SS format): ")
            processor.view_logs_by_timestamp(timestamp)
        
        elif choice == "3":
            timestamp = input("\nEnter timestamp to view logs (HH:MM:SS format): ")
            print("\nAvailable log types: INFO, ERROR, WARN, DEBUG, FATAL")
            log_type = input("Enter log type to filter by: ").upper()
            processor.view_logs_by_timestamp(timestamp, log_type)
        
        elif choice == "4":
            confirm = input("\nThis will delete all processed files. Are you sure? (y/n): ")
            if confirm.lower() == 'y':
                processor.reset_processing()
        
        elif choice == "5":
            print("\nExiting program...")
            break
        
        else:
            print("\nInvalid choice. Please try again.")

if __name__ == "__main__":
    main() 