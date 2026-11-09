<!-- Apple official documentation. Source of truth. -->
<!-- url: https://developer.apple.com/library/archive/technotes/tn2407/_index.html -->
<!-- fetched: 2026-10-20T00:54:37+00:00 -->
<!-- sha256: 069e9d59b436a20a9a561e97f14c192b425f49bc6386c4343d20f7d3e91ffb03 -->

Technical Note TN2407: iOS Code Signing Troubleshooting Index 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 

 
 
 
 
 
 
 Documentation Archive 
 Developer 
 Search 
 
 
 Search Documentation Archive 
 
 
 
 
 
 

 
 
 iOS Code Signing Troubleshooting Index

 
 PDF 
 Companion File 
 
 
 
 
 Table of Contents 
 

 Jump To… 

 
 Download Sample Code 
 

 
 
 
 
 

 
 
 
 
 
 
 
 
 Technical Note TN2407 iOS Code Signing Troubleshooting Index
 This document is an index of all of the iOS code signing troubleshooting information. The most important first step is to confirm that your project opts into automatic provisioning; this alone solves many code signing problems. The processes documented by Apple to Run on device, Beta Test, or Submit your app all involve code signing and their related code signing errors are covered in the subsequent sections. 

 
 

 
 
 
 Introduction 
 
 
 
 
 
 
 
 
 Ensure your project opts into Automatic Provisioning 
 
 
 
 
 
 
 
 
 Follow workflows documented by Apple to Run on device, Beta Test, or Submit your app 
 
 
 
 
 
 
 
 Run your app on device through Xcode 
 
 
 
 
 
 
 Beta Testing 
 
 
 
 
 
 
 Submitting to the App Store 
 
 
 
 
 
 
 Enterprise Distribution 
 
 
 
 
 
 
 Client and Contractor Distribution workflow 
 
 
 
 
 
 
 Enabling code signing on your other Macs 
 
 
 
 
 
 
 
 
 
 
 
 List of Code Signing Errors 
 
 
 
 
 
 
 
 Missing Certificate or Private Key errors 
 
 
 
 
 
 
 Provisioning Profile related errors 
 
 
 
 
 
 
 Installation Failure 
 
 
 
 
 
 
 Signature Verification Errors 
 
 
 
 
 
 
 Entitlements Errors 
 
 
 
 
 
 
 Other Errors 
 
 
 
 
 
 
 
 
 
 
 
 Document Revision History 
 
 
 
 
 
 
 

 Introduction
 The first step in troubleshooting iOS code signing errors is to configure your project for automatic provisioning. This is the currently recommended and supported workflow, whereas, the manual provisioning process of assigning specific code signing build settings yourself takes longer to do and it is often more problematic. 
 Back to Top Ensure your project opts into Automatic Provisioning
 The first step to troubleshoot iOS code signing failures is to opt your project into the modern code signing workflow. This is done by enabling automatic provisioning as covered the following guide: 
 • QA1814 - Setting up Xcode to automatically manage your provisioning profiles .
 Back to Top Follow workflows documented by Apple to Run on device, Beta Test, or Submit your app
 The second step in troubleshooting iOS code signing problems is to ensure you're following the proper workflow. The following is a complete list of workflows that involve code signing that are supported by Apple. 
 Run your app on device through Xcode
 • App Distribution Guide > Launching Your App on Devices 
 Beta Testing
 The following are two options to beta test your iOS app: 
 TestFlight Beta Testing 
 Using TestFlight to beta test iOS apps involves submitting an app to iTunes Connect that is signed with your App Store distribution provisioning profile. Once the app passes your beta tests you simply queue it for release to the App Store through iTunes Connect. This is the preferred method of beta testing because it does not require you to re-build or re-sign the submission for App Store publication. 
 • App Distribution Guide > Beta Testing iOS Apps > Distributing Your Prerelease Build Using TestFlight 
 Important:  Because apps submitted to TestFlight must be code signed with an App Store distribution provisioning profile, TestFlight cannot be used for the beta testing of Enterprise apps. 
 
 
 Ad Hoc Beta Testing 
 Important:  TestFlight is the preferred method of the distribution of beta test builds because it does not require you to re-code sign the app in order to submit it for App Store publication. Therefore, only use Ad Hoc beta testing if there is a compelling reason that you cannot use TestFlight. 
 
 To beta test iOS apps using Ad Hoc distribution, follow the steps in: 
 • App Distribution Guide > Beta Testing iOS Apps > Distributing Your Beta App Using Ad Hoc Provisioning 

 Submitting to the App Store
 Use the following process to submit your app for review: 
 • App Distribution Guide > Submitting Your App to the Store > Submitting Your App to the Store 
 Enterprise Distribution
 The documented process to distribute Enterprise apps is covered in the iOS Deployment Reference > Introduction 
 Client and Contractor Distribution workflow
 When a development contractor must distribute an app on behalf of the app client/owner, you must follow the workflow for build engineer distribution covered here: 
 • QA1763 - How can a build engineer distribute an app on behalf of the team? 
 Enabling code signing on your other Macs
 To enable code signing on your other Macs, OS X user accounts or partitions, use Xcode to export and import your code signing assets using the steps in: 
 • App Distribution Guide > Maintaining Your Signing Identities and Certificates > Exporting and Importing Certificates and Profiles 
 Back to Top List of Code Signing Errors
 The previous sections ensure that you opt into automatic provisioning and follow the workflow that involves code signing documented by Apple. For persistent code signing issues, consult the following list of code signing topics and their corresponding troubleshooting material. 
 Missing Certificate or Private Key errors
 These errors indicate that you are missing a required certificate or private key that is needed for code signing: 
 Missing Signing Identities No Matching Signing Identity or Provisioning Profiles Found The Private Key for Your Signing Identity Is Missing The Private Key for a Developer ID Certificate Is Missing Use the directions in the following guide to correct these kinds of problems: 
 • App Distribution Guide > Troubleshooting > Certificate Issues 
 Note:  For App Store teams, a majority of missing signing identity related issues can easily be resolved by recreating your certificates. See the following section for steps to do this: • App Distribution Guide > Maintaining Your Signing Identities and Certificates > Re-Creating Certificates and Updating Related Provisioning Profiles .
 
 Important:  For Enterprise teams which are missing their distribution certificate or its private key, you must instead consult the following document created specifically for this case: • QA1868 - Missing Enterprise Distribution Certificate Private Keys .
 
 Provisioning Profile related errors
 For general provisioning profile related issues such as: 
 Invalid Provisioning Profile Provisioning Profiles Installed on Your Device Are Invalid No Such Provisioning Profile Was Found See the following guide's recommendations to resolve them: 
 • App Distribution Guide > Troubleshooting > Provisioning Issues 
 Provisioning Profiles Appear Invalid in Member Center For answers to why your provisioning profile's status changes to Invalid, see the document: 
 • QA1878 - Resolving the Provisioning Profile Invalid Status 
 Installation Failure
 If your app is experiencing an installation failure, consult the resolutions that are covered in: 
 • TN2319 - Installation Failure Troubleshooting for iOS 
 Signature Verification Errors
 The following errors are related to app validation: 
 The bundle is not signed using an Apple submission certificate Missing or Invalid Signature. (rejection email) The bundle ... at bundle path ... is not signed using an Apple submission certificate For help with signature verification errors such as those listed above, use the recommendations and troubleshooting steps covered in: 
 • TN2318 - Troubleshooting Failed Signature Verification .
 Entitlements Errors
 Invalid Code Signing Entitlements Use the following guides to troubleshooting entitlement related errors: 
 • TN2415 - Entitlements Troubleshooting 

 • QA1798 - Checking Distribution Entitlements 

 None of valid provisioning profile allowed the specified entitlements This error indicates that Xcode expects a specific entitlement for your app but it cannot find a provisioning profile that contains that entitlement. There are different resolutions to this error depending on the entitlement that Xcode is looking for: 
 beta-reports-active 
 See the following document that covers this topic in detail: 
 • QA1830 - The beta-reports-active Entitlement . 

 All other entitlements 
 Sync Xcode's local provisioning profile library with the current state of the Certs, ID's and Profiles website using: 
 • Xcode > Preferences > Accounts > (your account) > View Details > "⟳" button. 

 Thoroughly analyze the Capabilities, Services, Entitlements your app uses with the guidance of: 
 • TN2415 - Entitlements Troubleshooting 

 
 Other Errors
 It's not always possible to infer the subject of all error messages. Check the following list of these types of general errors: 
 Your account already has a valid iOS distribution certificate This error primarily indicates that your development Mac is missing the distribution certificate and/or its private key. As a result, Xcode is attempting to generate a new distribution certificate / private key pair on your behalf, however, failed to do so because your team already has the maximum number of concurrently allowable distribution certificates. 
 Use one of the following options to resolve this error: 
 Transfer the missing certificate or private key to your Mac using the steps in section Enabling code signing on your other Macs .

 Revoke and re-create your distribution certificate using the steps in: 
 • App Distribution Guide > Maintaining Your Signing Identities and Certificates > Re-Creating Certificates and Updating Related Provisioning Profiles 
 Important:  Enterprise developers must take extra caution when resolving missing distribution certificate private keys, and should instead follow the process covered in a document created specifically for this situation. See QA1868 - Missing Enterprise Distribution Certificate Private Keys .
 
 
 Back to Top 
 Document Revision History

 Date Notes 2015-08-18 Link new entitlements troubleshooting document. 
 2015-07-21 Editorial update.
 2015-03-16 Moved Application-Identifier issues to the installation failure technical note.
 2015-02-03 added information about application-identifier and previous-application-identifiers entitlements
 2014-11-13 reorganization of contents
 2014-10-14 Including workflow for testing via iTunes Connect. 
 2014-10-02 New document that 
 provides a starting point to troubleshoot problems in workflows that involve code signing.
 

 
 
 

 
 Copyright © 2015 Apple Inc. All Rights Reserved. Terms of Use | Privacy Policy | Updated: 2015-08-18
