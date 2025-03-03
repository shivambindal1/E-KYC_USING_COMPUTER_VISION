import cv2
import os
import easyocr
import logging
import streamlit as st
from sqlalchemy import text
from preprocess import read_image, extract_id_card, save_image
#from ocr_engine import extract_text
#from postprocess1 import extract_information
from face_verification import detect_and_extract_face, face_comparison, get_face_embeddings
from mysqldb_operations import insert_records, fetch_records, check_duplicacy
from datetime import datetime

def extract_text(image_path, confidence_threshold=0.3, languages=['en']):
   
    reader = easyocr.Reader(languages)
    
    try:
       
        # Read the image and extract text
        result = reader.readtext(image_path)
        filtered_text = "|"  # Initialize an empty string to store filtered text
        for text in result:
            bounding_box, recognized_text, confidence = text
            if confidence > confidence_threshold:
                filtered_text += recognized_text + "|"  # Append filtered text with newline

        return filtered_text 
    except Exception as e:
        print("An error occurred during text extraction:", e)
        #logging.info(f"An error occurred during text extraction: {e}")
        return ""


def extract_information(data_string):
    # Split the data string into a list of words based on "|"
    updated_data_string = data_string.replace(".", "")
    words = [word.strip() for word in updated_data_string.split("|") if len(word.strip()) > 2]

    # Initialize the dictionary to store the extracted information
    extracted_info = {
        "ID": "",
        "Name": "",
        "Father's Name": "",
        "DOB": "",
        "ID Type": "PAN"
    }

    
    try:
        
        

        # #Define the regex pattern to match DOB in DD/MM/YYYY format
        # dob_pattern = r'\b\d{2}/\d{2}/\d{4}\b'

        # # Initialize dob_index to None
        # dob_index = None

        # # Loop through each word and check if it matches the DOB pattern    
        # for i, word in enumerate(words):
        #     # Use regex to search for the DOB pattern
        #     if re.match(dob_pattern, word):
        #         try:
        #             # Try to parse the found date using datetime.strptime
        #             datetime.strptime(word, "%d/%m/%Y")
        #             dob_index = i
        #             break
        #         except ValueError:
        #             # If there's an error, continue to the next word
        #             continue

        # # If a valid date of birth is found, extract it
        # if dob_index is not None:
        #     extracted_info["DOB"] = datetime.strptime(words[dob_index], "%d/%m/%Y")
        #     #print("Extracted Date of Birth:", extracted_info["DOB"].strftime('%Y-%m-%d'))
        # else:
        #     print("Error: Date of birth not found.")

        dob_index = None
        for i, word in enumerate(words):
            try:
                datetime.strptime(word, "%d/%m/%Y")
                dob_index = i
                break
            except ValueError:
                continue

        if dob_index is not None:
            extracted_info["DOB"] = datetime.strptime(words[dob_index], "%d/%m/%Y")
            extracted_info["DOB"] = datetime.date(extracted_info["DOB"])
        else:
            print("Error: Date of birth not found.")

        if('Name' not in data_string):
            #st.write(words)

            name_index = words.index("GOVT OF INDIA") + 1
            extracted_info["Name"] = words[name_index]

            fathers_name_index = name_index + 1
            extracted_info["Father's Name"] = words[fathers_name_index]

            id_number_index=0
            for i in words:
                if("Permanent Account" in i):
                    id_number_index=words.index(i)+1
            
            extracted_info["ID"] = words[id_number_index]

        else:
            #st.write(words)
            name_index = 6
            extracted_info["Name"] = words[name_index]

            fathers_name_index = name_index + 1
            extracted_info["Father's Name"] = words[fathers_name_index]

            id_number_index = 4
            extracted_info["ID"] = words[id_number_index]
            

    except ValueError:
        print("Error: Some required information is missing or incorrectly formatted.")

# Convert the dictionary to JSON format
# json_data = json.dumps([extracted_info])  # Convert a list containing the dictionary to match DataFrame format
    return extracted_info


logging_str = "[%(asctime)s: %(levelname)s: %(module)s]: %(message)s"
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(filename=os.path.join(log_dir,"ekyc_logs.log"), level=logging.INFO, format=logging_str, filemode="a")

# Set wider page layout
def wider_page():
    max_width_str = "max-width: 1200px;"
    st.markdown(
        f"""
        <style>
            .reportview-container .main .block-container{{ {max_width_str} }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    logging.info("Page layout set to wider configuration.")


# Sidebar
def sidebar_section():
    st.sidebar.title("Select ID Card Type")
    option = st.sidebar.selectbox("", ("PAN", "AADHAR "))
    logging.info(f"ID card type selected: {option}")
    return option

# Header
def header_section(option):
    if option == "Aadhar":
        st.title("Registration Using Aadhar Card")
        logging.info("Header set for Aadhar Card registration.")
    elif option == "PAN":
        st.title("Registration Using PAN Card")
        logging.info("Header set for PAN Card registration.")

# Main content
def main_content(image_file, face_image_file, conn):
    if image_file is not None:
        face_image = read_image(face_image_file, is_uploaded=True)
        logging.info("Face image loaded.")
        if face_image is not None:
            image = read_image(image_file, is_uploaded=True)
            logging.info("ID card image loaded.")
            image_roi, name = extract_id_card(image)
            logging.info("ID card ROI extracted.")
            
            face_image_path1 = save_image(face_image, "face_image.jpg", path="data\\02_intermediate_data")
            face_image_path2 = detect_and_extract_face(name)
            logging.info("Faces extracted and saved.")
            is_face_verified = face_comparison(image1_path=face_image_path1, image2_path=face_image_path2)
            logging.info(f"Face verification status: {'successful' if is_face_verified else 'failed'}.")

            if is_face_verified:
                extracted_text = extract_text(image_roi)
                
                text_info = extract_information(extracted_text)
                
                logging.info("Text extracted and information parsed from ID card.")
                records = fetch_records(text_info)
                if records.shape[0] > 0:
                    st.write(records.shape)
                    st.write(records)
                is_duplicate = check_duplicacy(text_info)
                if is_duplicate:
                    st.write(f"User already present with ID {text_info['ID']}")
                else: 
                    st.write(text_info)
                        # Try to parse the DOB if it's a string
                    if isinstance(text_info['DOB'], str):
                        text_info["DOB"]=datetime.strptime(text_info["DOB"],'%d/%m/%Y')
                        text_info['DOB'] = text_info['DOB'].strftime('%Y-%m-%d')
                        text_info['Embedding'] =  get_face_embeddings(face_image_path1)
                        insert_records(text_info)
                        logging.info(f"New user record inserted: {text_info['ID']}")
                        
                    else:

                        text_info['DOB'] = text_info['DOB'].strftime('%Y-%m-%d')
                        text_info['Embedding'] =  get_face_embeddings(face_image_path1)
                        insert_records(text_info)
                        logging.info(f"New user record inserted: {text_info['ID']}")
                        
            else:
                st.error("Face verification failed. Please try again.")

        else:
            st.error("Face image not uploaded. Please upload a face image.")
            logging.error("No face image uploaded.")

    else:
        st.warning("Please upload an ID card image.")
        logging.warning("No ID card image uploaded.")

# Main function setup as previously provided...
def main():
    # Initialize connection.
    conn = st.connection('mysql', type='sql')
    wider_page()
    option = sidebar_section()
    header_section(option)
    image_file = st.file_uploader("Upload ID Card")
    if image_file is not None:
        face_image_file = st.file_uploader("Upload Face Image")
        main_content(image_file, face_image_file, conn)

if __name__ == "__main__":
    main()