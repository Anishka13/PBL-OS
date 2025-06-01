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
        self.original_size = os.path.getsize(input_file)
        self.chunk_sizes = {}  # Store original and compressed sizes for each chunk
        self.index_sizes = {}  # Store original and compressed sizes for index files
        self.total_original_size = 0  # Will include original chunks + original index files
        self.total_compressed_size = 0  # Will include compressed chunks + compressed index files
        
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

    def get_total_sizes(self):
        """Get the total sizes and space savings."""
        # Calculate total original size (input file)
        input_file_size = self.original_size
        
        # Calculate total size of all compressed files (chunks + indexes)
        compressed_size = 0
        for filename in os.listdir(self.compressed_chunks_dir):
            if filename.endswith('.gz'):
                compressed_size += os.path.getsize(os.path.join(self.compressed_chunks_dir, filename))
        for filename in os.listdir(self.compressed_index_dir):
            if filename.endswith('.gz'):
                compressed_size += os.path.getsize(os.path.join(self.compressed_index_dir, filename))
        
        # Calculate space savings
        space_saved = input_file_size - compressed_size
        savings_percentage = (space_saved / input_file_size) * 100 if input_file_size > 0 else 0
        
        return {
            'input_file_size': input_file_size,
            'total_compressed_size': compressed_size,
            'space_saved': space_saved,
            'savings_percentage': savings_percentage,
            'chunk_details': self.chunk_sizes,
            'index_details': self.index_sizes
        }

    def get_total_size_comparison(self):
        """Calculate and compare original file size vs total size of all processed files."""
        # Original file size
        original_size = self.original_size
        
        # Calculate total size of all compressed chunks and index files
        total_processed_size = 0
        chunk_details = {}
        
        # Get details for each chunk
        for filename in os.listdir(self.output_dir):
            if filename.endswith('.log'):
                time_key = filename[:-4]  # Remove .log extension
                chunk_path = os.path.join(self.output_dir, filename)
                compressed_chunk_path = os.path.join(self.compressed_chunks_dir, filename + '.gz')
                index_path = os.path.join(self.compressed_index_dir, time_key + '.json.gz')
                
                # Get sizes
                original_size_chunk = os.path.getsize(chunk_path)
                compressed_size = os.path.getsize(compressed_chunk_path)
                index_size = os.path.getsize(index_path)
                
                # Store details for this chunk
                chunk_details[time_key] = {
                    'original_size': original_size_chunk,
                    'compressed_size': compressed_size,
                    'index_size': index_size
                }
                
                total_processed_size += compressed_size + index_size
        
        return {
            'original_size': original_size,
            'total_processed_size': total_processed_size,
            'difference': original_size - total_processed_size,
            'chunk_details': chunk_details
        }

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
            
            # Store original chunk size
            original_size = os.path.getsize(log_file)
            self.chunk_sizes[time_key] = {'original': original_size}
            
            # Write index file
            index_file = os.path.join(self.index_dir, f"{time_key}.json")
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "total_lines": len(logs_by_second[time_key]),
                    "entries": indexes_by_second[time_key]
                }, f, indent=2)
            
            # Store original index size
            index_size = os.path.getsize(index_file)
            self.index_sizes[time_key] = {'original': index_size}
            
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
                
                # Store compressed chunk size
                time_key = filename[:-4]  # Remove .log extension
                compressed_size = os.path.getsize(output_path)
                if time_key in self.chunk_sizes:
                    self.chunk_sizes[time_key]['compressed'] = compressed_size
                
                print(f"Compressed: {filename}")

        # Compress index files
        for filename in os.listdir(self.index_dir):
            if filename.endswith('.json'):
                input_path = os.path.join(self.index_dir, filename)
                output_path = os.path.join(self.compressed_index_dir, filename + '.gz')
                
                with open(input_path, 'rb') as f_in:
                    with gzip.open(output_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Store compressed index size
                time_key = filename[:-5]  # Remove .json extension
                compressed_size = os.path.getsize(output_path)
                if time_key in self.index_sizes:
                    self.index_sizes[time_key]['compressed'] = compressed_size
                
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

    def view_logs_by_timerange(self, start_timestamp, end_timestamp, log_type=None):
        """View logs within a time range by decompressing the files temporarily.
        Optional log_type parameter to filter logs by type (INFO, ERROR, etc.)"""
        try:
            # Parse the timestamps to validate format
            start_time = datetime.strptime(start_timestamp, '%H:%M:%S')
            end_time = datetime.strptime(end_timestamp, '%H:%M:%S')
            
            # Convert timestamps to file format
            start_key = start_timestamp.replace(':', '_')
            end_key = end_timestamp.replace(':', '_')
            
            # Get all log files in the compressed directory
            log_files = sorted([f for f in os.listdir(self.compressed_chunks_dir) if f.endswith('.log.gz')])
            
            if not log_files:
                print("No log files found")
                return
            
            # Filter files within the time range
            relevant_files = []
            for log_file in log_files:
                file_time = log_file.replace('.log.gz', '').replace('_', ':')
                try:
                    file_time_obj = datetime.strptime(file_time, '%H:%M:%S')
                    if start_time <= file_time_obj <= end_time:
                        relevant_files.append(log_file)
                except ValueError:
                    continue
            
            if not relevant_files:
                print(f"No logs found between {start_timestamp} and {end_timestamp}")
                return
            
            # Create a temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                all_logs = []
                total_lines = 0
                
                # Process each relevant file
                for log_file in relevant_files:
                    time_key = log_file.replace('.log.gz', '')
                    compressed_log = os.path.join(self.compressed_chunks_dir, log_file)
                    compressed_index = os.path.join(self.compressed_index_dir, f"{time_key}.json.gz")
                    
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
                        
                        # Update content
                        log_content = filtered_lines
                    
                    all_logs.extend(log_content)
                    total_lines += len(log_content)
                
                # Display the contents
                print(f"\nLogs between {start_timestamp} and {end_timestamp}" + 
                      (f" (filtered by {log_type})" if log_type else ""))
                print(f"Total log entries: {total_lines}")
                print("-" * 80)
                
                # Display the logs
                for line in all_logs:
                    if line.strip():  # Only print non-empty lines
                        print(line.strip())
                
                print("-" * 80)
            
        except ValueError as e:
            print(f"Invalid timestamp format: {str(e)}")
        except Exception as e:
            print(f"Error reading logs: {str(e)}")

def main():
    # Use your specific log file
    input_file = "Hadoop_2k (1).log"
    processor = LogProcessor(input_file)
    
    while True:
        print("\nLog Viewer Menu:")
        print("1. Process and compress log files")
        print("2. View logs by timestamp")
        print("3. View filtered logs by timestamp and type")
        print("4. View logs by time range")
        print("5. Reset Processing (Use after modifying the log file)")
        print("6. Exit")
        
        choice = input("Enter your choice (1-6): ")
        
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
            start_timestamp = input("\nEnter start timestamp (HH:MM:SS format): ")
            end_timestamp = input("\nEnter end timestamp (HH:MM:SS format): ")
            processor.view_logs_by_timerange(start_timestamp, end_timestamp)
        
        elif choice == "5":
            confirm = input("\nThis will delete all processed files. Are you sure? (y/n): ")
            if confirm.lower() == 'y':
                processor.reset_processing()
        
        elif choice == "6":
            print("\nExiting program...")
            break
        
        else:
            print("\nInvalid choice. Please try again.")

if __name__ == "__main__":
    main() 