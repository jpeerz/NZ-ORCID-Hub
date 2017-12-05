*** Settings ***
Documentation     Mailinator Service Resource File
Library             SeleniumLibrary     run_on_failure=Nothing
Library           String
Resource          resource.robot
Variables         variables.py

*** Keywords ***
Go To Mailinator Inbox
    [Arguments]     ${email}
    ${email} =      Fetch From Left     ${email}    @
    ${url} =        Set Variable    ${MAILINATOR_START_URL}${email}${MAILINATOR_END_URL}
    Go To       ${url}

Open Newest Email
    Click Element       //div[@title="FROM"]

OrcidHub Email
    ${heading}

Orcid Email
    ${heading} =    //div[@id=]

Deactivate Orcid Account
    Select Frame    xpath=(//iframe[@id='msg_body']|//frame[@id='msg_body'])
    # Sleeping for 1 second to allow for mailinator to open the email.
    Sleep   1 second
    Click Link      xpath=(//a[contains(@href,'confirm-deactivate-orcid')])