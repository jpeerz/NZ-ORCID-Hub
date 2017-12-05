# Regression Testing Design
 - All Regression tests are located in the tests directory with the .robot extension.
 - Keywords used by the regression tests are stored in the tests/resources directory.
 - Any example data to be used during testing should be stored in the tests/resources/example-data directory.
 - All variables to be used should be declared in the tests/resources/variables.py as either plaintext or an Environment Variable. (This file is automatically imported by the resource.robot).
 - All regressions tests should import the resource.robot file as this describes the Setup & Teardown of each test.

## Regression Test Keyword Rules
 - Each keyword file should contain keywords related to the service/operation of the name of the file.
 - Keywords should be standalone and not depend on keywords in other resource files. (They can however depend on keywords in the same resource file).
 - Each service should have its own folder if it contains multiple operations.
 - If the service has only one operation then the resource file should be named after the service.

# Regression Tests
## Completed
### Authentication via TUAKIRI (_Any Users_)
 - Login of a User.
 - New user (creates an entry in user table, link to the organisation entry).
 - Returning user.
 - Entering invalid data (all kinds of corner cases).

### Organisation on-boarding (organisation invitation to join the Hub) (_Hub Admin_)
 - Creation & Removal of Organisation.

## In Progress
### Organisation on-boarding (organisation invitation to join the Hub) (_Hub Admin_)
 - Creation & Removal of Organisation.
 - Sending invitation to a user not yet registered.
 - Sending invitation to an exiting user.
 - Re-sending an invitation (generating a new token).
 - Entering invalid data (all kinds of corner cases).

### Organisation on-boarding (adding organisation credentials to the Hub) (_Org.Admin_)
 - Attempt to re-use the invitation token.
 - Entering invalid data (all kinds of corner cases).

### Organisation administrator invitation (_Hub Admin_)
 - Sending invitation to a user not yet registered.
 - Sending invitation to an exiting user.
 - Re-sending an invitation (generating a new token).
 - Attempt to re-use the invitation token.

### Organisation (not connected to TUAKIRI) administrator invitation (_Hub Admin_)
 - Sending invitation to a user not yet registered.
 - Sending invitation to an exiting user.
 - Re-sending an invitation (generating a new token).
 - Attempt to re-use the invitation token.

## Not Started
### Authentication via TUAKIRI (_Any Users_)
 - Returning user after update IdP (IAM) profile, e.g., preferred name, affiliation nature (staff, student, etc.).
 - Returning user after update IdP (IAM) profile: email address.

### User/Researcher affiliation (_Any User_)

### User profile update (adding new entries, deletion and update of records) (_Org.Admin_)

### Supporting Functionality
 - Organisation information import (_Hub.Admin_).
 - User Summary (_Hub.Admin_).
 - Invitation Summary (_Hub.Admin_).