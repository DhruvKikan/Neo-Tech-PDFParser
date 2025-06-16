Used AWS EC2 for deployment and testing live

DON'T FORK OR TRY TO RUN LOCALLY.

The main pdf processing requires tesseract and OpenCV for text processing. 

After text extraction, basic pre-processing is done utilizing regular expressions.
After pre-processing, the text is fed into a LLM which extracts and returns the information in a parsed manner based on the template.
Uploading JDs of jobs and scoring candidates on the basis of the JD has been added.
