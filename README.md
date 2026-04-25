# Marksheet Detection & Confidence Analyzer

## Project Overview
**Marksheet Detection & Confidence Analyzer** is a web application that extracts and analyzes key data from marksheets. It provides a clean, user-friendly interface for uploading documents (PDFs or images) and uses a FastAPI backend to process the file, extract relevant information like student details and subject marks, and present the data with an associated confidence score.  

This project is designed to handle different marksheet formats, making it a versatile tool for data extraction.

----

## Features
- **Document Upload:** Supports uploading marksheets in PDF and common image formats.  
- **Intelligent Extraction:** Uses regular expressions and OCR (Optical Character Recognition) to accurately parse text and extract information.  
- **Adaptive Logic:** The backend intelligently adapts its extraction method based on the marksheet's format.  
- **Structured Results:** Displays extracted data in a clean, organized table with sections for student details, subject marks, and overall results.  
- **Confidence Scores:** Provides a confidence score for each extracted data point, helping users gauge the accuracy of the results.  
- **Modern UI:** Clean, responsive frontend built with HTML and CSS.
- **Deployment:** Used Render to make it publicly testable.
- 
----
