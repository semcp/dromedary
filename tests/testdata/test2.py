from datetime import date, timedelta                                                      
from pydantic import BaseModel, EmailStr                                                  
# 1. Fetch the most recent received email                                                 
received = get_received_emails()                                                          
last_email = received[-1]                                                                 
email_body = last_email["body"]                                                           
# 2. Extract Bob's email address from that email                                          
class EmailExtraction(BaseModel):                                                         
    email: EmailStr                                                                       
extracted = query_ai_assistant(                                                           
    "Extract Bob's email address from the following email body:\n\n" + email_body,        
    EmailExtraction                                                                       
)

bob_email = extracted.email
                                                                                          
# 3. Compute tomorrow's date                                                              
today_iso = get_current_day()                                                             
today = date.fromisoformat(today_iso)                                                     
tomorrow = today + timedelta(days=1)                                                      
tomorrow_str = tomorrow.isoformat()                                                       
                                                                                          
# 4. Send the reminder email                                                              
subject = f"Reminder: Meeting on {tomorrow_str}"                                          
body = (                                                                                  
    f"Hello Bob,\n\n"                                                                     
    f"This is a friendly reminder about our meeting scheduled for {tomorrow_str}.\n\n"    
    f"Best regards,"                                                                      
)                                                                                         

send_email([bob_email], subject, body)
