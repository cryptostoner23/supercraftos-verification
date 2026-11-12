<!-- Apple official documentation. Source of truth. -->
<!-- url: https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/ExtensionScenarios.html -->
<!-- fetched: 2026-10-20T00:53:52+00:00 -->
<!-- sha256: ece63524ffbfef71915744d85bc2ec051c862a702ede8a6535f61d8fc220c991 -->

App Extension Programming Guide: Handling Common Scenarios 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 

 
 
 
 
 

 
 
 
 
 
 Documentation Archive
 
 

 Developer 

 
 

 
 
 
 App Extension Programming Guide 
 

 
 
 

 
 
 

 
 
 
 
 
 
 
 App Extension Essentials 
 
 
 App Extensions Increase Your Impact 
 

 
 Understand How an App Extension Works 
 

 
 Creating an App Extension 
 

 
 Handling Common Scenarios 
 

 
 

 
 App Extension Types 
 
 
 Action 
 

 
 Audio Unit 
 

 
 Content Blocker 
 

 
 Custom Keyboard 
 

 
 Document Provider 
 

 
 Finder Sync 
 

 
 Photo Editing 
 

 
 Share 
 

 
 Today 
 

 
 

 
 Revision History 
 
 
 Document Revision History 
 

 
 

 
 

 
 
 
 On This Page 
 
 
 
 
 
 
 
 Using an Embedded Framework to Share Code 
 

 
 Sharing Data with Your Containing App 
 

 
 Accessing a Webpage 
 

 
 Performing Uploads and Downloads 
 

 
 Declaring Supported Data Types for a Share or Action Extension 
 

 
 Deploying a Containing App to Older Versions of iOS 
 

 
 
 

 
 
 
 
 

 Handling Common Scenarios

 
 
 
 

 
 As you write custom code that performs your app extension’s task, you may need to handle some scenarios that are common to many types of extensions. Use the code and recommendations in this chapter to help you implement your solutions.

 

 
 
 Using an Embedded Framework to Share Code

 
 

 
 You can create an embedded framework to share code between your app extension and its containing app. For example, if you develop an image filter for use in your Photo Editing extension as well as in its containing app, put the filter’s code in a framework and embed the framework in both targets.

 
 

 
 Make sure your embedded framework does not contain APIs unavailable to app extensions, as described in Some APIs Are Unavailable to App Extensions . If you have a custom framework that does contain such APIs, you can safely link to it from your containing app but cannot share that code with the app’s contained extensions. The App Store rejects any app extension that links to such frameworks or that otherwise uses unavailable APIs.

 
 To configure an app extension target to use an embedded framework, set the target’s “Require Only App-Extension-Safe API” build setting to Yes. If you don’t, Xcode reminds you to do so by displaying the warning “linking against dylib not safe for use in application extensions” .

 
 
 
 Important
 

 A containing app that links to an embedded framework must include the arm64 (iOS) or x86_64 (OS X) architecture build setting or it will be rejected by the App Store. (As described in Creating an App Extension , all app extensions must include the appropriate 64-bit architecture build setting.)
 

 
 
 
 When configuring your Xcode project, you must choose “Frameworks” as the destination for your embedded framework in the Copy Files build phase.

 
 
 
 Important
 

 Always choose “Frameworks” as your Copy Files build phase destination. If you instead choose the “SharedFramework” destination, the App Store will reject your submission.
 

 
 
 
 You can make a containing app available to users running iOS 7 or earlier, but then must take precautions to safely link embedded frameworks when running in iOS 8 or later. Read Deploying a Containing App to Older Versions of iOS for details.

 
 For more on creating and using embedded frameworks, watch the WWDC 2014 video “Building Modern Frameworks,” available at https://developer.apple.com/videos/wwdc/2014 .

 
 
 
 
 Sharing Data with Your Containing App

 
 

 
 

 
 Even though an app extension bundle is nested within its containing app’s bundle, the running app extension and containing app have no direct access to each other’s containers.

 
 
 
 Background
 

 To learn about containers, read About the iOS File System in File System Programming Guide .
 

 
 
 
 You can, however, enable data sharing. For example, you might want to allow your app extension and its containing app to share a single large set of data, such as prerendered assets. 

 
 To enable data sharing, use Xcode or the Developer portal to enable app groups for the containing app and its contained app extensions. Next, register the app group in the portal and specify the app group to use in the containing app. To learn about working with app groups, see Adding an App to an App Group .

 
 After you enable app groups, an app extension and its containing app can both use the NSUserDefaults API to share access to user preferences. To enable this sharing, use the initWithSuiteName: method to instantiate a new NSUserDefaults object, passing in the identifier of the shared group. For example, a Share extension might update the user’s most recently used sharing account, using code like this:

 
 
 
 
 
 // Create and share access to an NSUserDefaults object 

 NSUserDefaults *mySharedDefaults = [[NSUserDefaults alloc] initWithSuiteName: @"com.example.domain.MyShareExtension"]; 

 

 // Use the shared user defaults object to update the user's account 

 [mySharedDefaults setObject:theAccountName forKey:@"lastAccountName"]; 

 
 
 
 
 Figure 4-1 shows how an extension and its containing app can use a shared container to share data.

 
 

 
 
 Figure 4-1 An app extension’s container is distinct from its containing app’s container 
 
 
 

 
 
 
 Important
 

 You must set up a shared container if your app extension uses the NSURLSession class to perform a background upload or download, so that both the extension and its containing app can access the transferred data. To learn how to perform an upload or download in the background, see Performing Uploads and Downloads .
 

 
 
 
 When you set up a shared container, the containing app—and each contained app extension that you allow to participate in data sharing—have read and write access to the shared container. To avoid data corruption, you must synchronize data accesses. 

 
 Use Core Data, SQLite, or Posix locks to help coordinate data access in a shared container.

 
 

 
 

 
 
 
 Version Note
 

 In iOS 8.2 and later, you can alternatively employ the UIDocument class to coordinate shared data access.
 

 
 In iOS 9 and later, you can employ the NSFileCoordinator class directly for shared data access, but if you do this you must remove your NSFilePresenter objects when your app extension transitions into the background.

 
 
 

 
 

 
 

 
 
 
 
 Accessing a Webpage

 
 In Share extensions (on both platforms) and Action extensions (iOS only), you can give users access to web content by asking Safari to run a JavaScript file and return the results to the extension. You can also use the JavaScript file to access a webpage before your extension runs (on both platforms), or to access or modify the webpage after your extension completes its task (iOS only). For example, a Share extension can help users share content from a webpage, or an Action extension in iOS might display a translation of the user’s current webpage.

 
 To add webpage access and manipulation to your app extension, perform the following steps:

 
 
 Create a JavaScript file that includes a global object named ExtensionPreprocessingJS . Assign a new instance of your custom JavaScript class to this object.

 
 In the NSExtensionActivationRule dictionary in your app extension’s Info.plist file, give the NSExtensionActivationSupportsWebPageWithMaxCount key a nonzero value. (To learn more about the activation rule dictionary, see Declaring Supported Data Types for a Share or Action Extension .)

 
 When your app extension starts, use the NSItemProvider class to get the results returned by the execution of the JavaScript file.

 
 In an iOS app extension, pass values to the JavaScript file if you want Safari to modify the webpage when your extension completes its task. (You use the NSItemProvider class in this step, too.)

 
 To tell Safari that your app extension includes a JavaScript file, add the NSExtensionJavaScriptPreprocessingFile key to the NSExtensionAttributes dictionary. The value of the key should be the file that you want Safari to load before your extension starts. For example:

 
 
 
 
 
 <key>NSExtensionAttributes</key> 

 <dict> 

 <key>NSExtensionJavaScriptPreprocessingFile</key> 

 <string>MyJavaScriptFile</string> <!-- Do not include the ".js" filename extension --> 

 </dict> 

 
 
 
 
 On both platforms, your custom JavaScript class can define a run() function that Safari invokes as soon as it loads the JavaScript file. In the run() function, Safari provides an argument named completionFunction , with which you can pass results to your app extension in the form of a key-value object.

 
 In iOS, you can also define a finalize() function that Safari invokes when your app extension calls completeRequestReturningItems:completion: at the end of its task. A finalize() function can use items your extension passes in completeRequestReturningItems:completion: to change the webpage as desired. 

 
 For example, if your iOS app extension needs the base URI of a webpage when it starts and it changes the background color of the webpage when it stops, you might write JavaScript code like that shown in Listing 4-1 .

 
 
 Listing 4-1 Example run() and finalize() functions 
 
 
 
 var MyExtensionJavaScriptClass = function() {}; 

 

 MyExtensionJavaScriptClass.prototype = { 

 run: function(arguments) { 

 // Pass the baseURI of the webpage to the extension. 

 arguments.completionFunction({"baseURI": document.baseURI}); 

 }, 

 

 // Note that the finalize function is only available in iOS. 

 finalize: function(arguments) { 

 // arguments contains the value the extension provides in [NSExtensionContext completeRequestReturningItems:completion:]. 

 // In this example, the extension provides a color as a returning item. 

 document.body.style.backgroundColor = arguments["bgColor"]; 

 } 

 }; 

 

 // The JavaScript file must contain a global object named "ExtensionPreprocessingJS". 

 var ExtensionPreprocessingJS = new MyExtensionJavaScriptClass; 

 
 
 
 
 On both platforms, you need to write code to handle the values that get passed back from your run() function. To get the dictionary of results, specify the kUTTypePropertyList type identifier in the NSItemProvider method loadItemForTypeIdentifier:options:completionHandler: . In the dictionary, use the NSExtensionJavaScriptPreprocessingResultsKey key to get the result item. For example, to get the base URI passed in the run() function in Listing 4-1 , you might use code like this:

 
 
 
 
 
 [imageProvider loadItemForTypeIdentifier:kUTTypePropertyList options:nil completionHandler:^(NSDictionary *item, NSError *error) { 

 NSDictionary *results = (NSDictionary *)item; 

 NSString *baseURI = [[results objectForKey:NSExtensionJavaScriptPreprocessingResultsKey] objectForKey:@"baseURI"]; 

 }]; 

 
 
 
 
 To pass a value to the finalize() function when your iOS app extension finishes its task, use the NSItemProvider initWithItem:typeIdentifier: method to pack the value in the dictionary for the NSExtensionJavaScriptFinalizeArgumentKey key. For example, to specify red for the background color used in the finalize() function in Listing 4-1 , your extension might use code like this:

 
 
 
 
 
 NSExtensionItem *extensionItem = [[NSExtensionItem alloc] init]; 

 extensionItem.attachments = @[[[NSItemProvider alloc] initWithItem: @{NSExtensionJavaScriptFinalizeArgumentKey: @{@"bgColor":@"red"}} typeIdentifier:(NSString *)kUTTypePropertyList]]; 

 [[self extensionContext] completeRequestReturningItems:@[extensionItem] completion:nil]; 

 
 
 
 
 
 
 
 
 Performing Uploads and Downloads

 
 

 
 

 
 Users tend to return to the host app immediately after they finish their task in your app extension. If the task involves a potentially lengthy upload or download, you need to ensure that it can finish after your extension gets terminated. To perform an upload or download, use the NSURLSession class to create a URL session and initiate a background upload or download task.

 
 
 
 Note
 

 Recall that other types of background tasks, such as supporting VoIP or playing background audio, are not available to app extensions. For more information, see Respond to the Host App’s Request .
 

 
 
 
 After your app extension initiates the upload or download task, the extension can complete the host app’s request and be terminated without affecting the outcome of the task. To learn more about how an extension handles the request from a host app, see Respond to the Host App’s Request . In iOS, if your extension isn’t running when a background task completes, the system launches your containing app in the background and calls the application:handleEventsForBackgroundURLSession:completionHandler: app delegate method.

 
 
 
 Important
 

 If your app extension initiates a background NSURLSession task, you must also set up a shared container that both the extension and its containing app can access. Use the sharedContainerIdentifier property of the NSURLSessionConfiguration class to specify an identifier for the shared container so that you can access it later.
 

 
 Refer to Sharing Data with Your Containing App for guidance on setting up a shared container.

 
 
 Listing 4-2 shows one way to configure a URL session and use it to initiate a download.

 
 
 Listing 4-2 An example of configuring an NSURLSession object and starting a download 
 
 
 
 NSURLSession *mySession = [self configureMySession]; 

 NSURL *url = [NSURL URLWithString:@"http://www.example.com/LargeFile.zip"]; 

 NSURLSessionTask *myTask = [mySession downloadTaskWithURL:url]; 

 [myTask resume]; 

 

 - (NSURLSession *) configureMySession { 

 if (!mySession) { 

 NSURLSessionConfiguration* config = [NSURLSessionConfiguration backgroundSessionConfigurationWithIdentifier:@“com.mycompany.myapp.backgroundsession”]; 

 // To access the shared container you set up, use the sharedContainerIdentifier property on your configuration object. 

 config.sharedContainerIdentifier = @“com.mycompany.myappgroupidentifier”; 

 mySession = [NSURLSession sessionWithConfiguration:config delegate:self delegateQueue:nil]; 

 } 

 return mySession; 

 } 

 
 
 
 
 

 
 Because only one process can use a background session at a time, you need to create a different background session for the containing app and each of its app extensions. (Each background session should have a unique identifier.) It’s recommended that your containing app only use a background session that was created by one of its extensions when the app is launched in the background to handle events for that extension. If you need to perform other network-related tasks in your containing app, create different URL sessions for them.

 
 If you need to complete the host app’s request before you initiate a background URL session, make sure that the code that creates and uses the session is efficient. After your app extension calls completeRequestReturningItems:completionHandler: to tell the host app that its request is complete, the system can terminate your extension at any time.

 
 
 
 
 Declaring Supported Data Types for a Share or Action Extension

 
 In your Share or Action extension, it’s likely that you can work with some types of data but not others. To ensure that a host app offers your extension only when the user has selected data of a type that you support, add the NSExtensionActivationRule key to your extension’s Info.plist property list file. You can also use this key to specify a maximum number of items of each type that your extension can handle. 

 
 When your extension runs, the system compares the NSExtensionActivationRule key’s values with the information in an extension item’s attachments property. For a complete list of keys you can use with this key, see Action Extension Keys .

 
 For example, to declare that your Share extension can support up to ten images, one movie, and one webpage URL, you might use the following dictionary for the value of the NSExtensionAttributes key:

 
 
 
 
 
 <key>NSExtensionAttributes</key> 

 <dict> 

 <key>NSExtensionActivationRule</key> 

 <dict> 

 <key>NSExtensionActivationSupportsImageWithMaxCount</key> 

 <integer>10</integer> 

 <key>NSExtensionActivationSupportsMovieWithMaxCount</key> 

 <integer>1</integer> 

 <key>NSExtensionActivationSupportsWebURLWithMaxCount</key> 

 <integer>1</integer> 

 </dict> 

 </dict> 

 
 
 
 
 If you don’t support a particular data type, use 0 for the value of the corresponding key or remove the key from your NSExtensionActivationRule dictionary.

 
 
 
 Note
 

 If your Share or iOS Action extension needs to access a webpage, you must include the NSExtensionActivationSupportsWebPageWithMaxCount key with a nonzero value. (To learn how to use JavaScript to access a webpage from your extension, see Accessing a Webpage .)
 

 
 
 
 The keys in the NSExtensionActivationRule dictionary are sufficient to meet the filtering needs of typical app extensions. If you need to do more complex or more specific filtering, such as distinguishing between public.url and public.image , you can create a predicate statement. Then, use the bare string that represents the predicate as the value of the NSExtensionActivationRule key. (At runtime, the system compiles this string into an NSPredicate object.)

 
 For example, an app extension item's attachments property can specify a PDF file like this:

 
 
 
 
 
 {extensionItems = ({ 

 attachments = ({ 

 registeredTypeIdentifiers = ( 

 "com.adobe.pdf", 

 "public.file-url" 

 ); 

 }); 

 })} 

 
 
 
 
 To specify that your app extension can handle exactly one PDF file, you might create a predicate string like this:

 
 
 
 
 
 SUBQUERY ( 

 extensionItems, 

 $extensionItem, 

 SUBQUERY ( 

 $extensionItem.attachments, 

 $attachment, 

 ANY $attachment.registeredTypeIdentifiers UTI-CONFORMS-TO "com.adobe.pdf" 

 ).@count == $extensionItem.attachments.@count 

 ).@count == 1 

 
 
 
 
 Here is an example of a more complex predicate statement:

 
 
 
 
 
 SUBQUERY ( 

 extensionItems, 

 $extensionItem, 

 SUBQUERY ( 

 $extensionItem.attachments, 

 $attachment, 

 ANY $attachment.registeredTypeIdentifiers UTI-CONFORMS-TO "org.appextension.action-one" || 

 ANY $attachment.registeredTypeIdentifiers UTI-CONFORMS-TO "org.appextension.action-two" 

 ).@count == $extensionItem.attachments.@count 

 ).@count == 1 

 
 
 
 
 This statement iterates over an array of NSExtensionItem objects, and secondarily over the attachments array in each extension item. For each attachment, the predicate evaluates the uniform type identifier (UTI) for each representation in the attachment. When an attachment representation UTI conforms to any of of two different specified UTIs (which you see on the right-hand side of each UTI-CONFORMS-TO operator), collect that UTI for the final comparison test. The final line returns TRUE if the app extension was given exactly one extension item attachment with a supported UTI.

 
 During development only, you can use the TRUEPREDICATE constant (which always evaluates to true ) as a stub predicate statement, to test your code path before you implement your predicate statement.

 
 
 
 Important
 

 Before you submit your containing app to the App Store, be sure to replace all uses of TRUEPREDICATE stub predicates with functional predicate statements or with NSExtensionActivationRule keys. If any app extensions in your containing app include the string TRUEPREDICATE , the app will be rejected.
 

 
 
 
 To learn more about the syntax of predicate statements, see Predicate Format String Syntax in Predicate Programming Guide .

 
 
 
 
 Deploying a Containing App to Older Versions of iOS

 
 

 
 

 
 

 
 

 
 

 
 

 
 

 
 

 
 If you link to an embedded framework from your containing app, you can still deploy it to versions of iOS older than 8.0, even though embedded frameworks are not available in those versions.

 
 The mechanism that lets you do this is the dlopen command, which you use to conditionally link and load a framework bundle. You employ this command as an alternative to the build-time linking you can specify in the Xcode General or Build Phases target editor. The main idea is to link embedded frameworks into your containing app only when running in iOS 8.0 or newer. 

 
 You must use Objective-C, not Swift, in your code statements that conditionally load a framework bundle. The rest of your app can be written in either language, and the embedded framework itself can likewise be written in either language.

 
 After calling dlopen , access the embedded framework classes using the following type of statement:

 
 
 
 
 
 MyLoadedClass *loadedClass = [[NSClassFromString (@"MyClass") alloc] init]; 

 
 
 
 
 
 
 Important
 

 If your containing app target links to an embedded framework, it must include the arm64 architecture or it will be rejected by the App Store.
 

 
 
 
 To set up an app extension Xcode project to take advantage of conditional linking 

 
 
 For each of your contained app extensions, set the deployment target to be iOS 8.0 or later, as usual.

 
 Do this in the “Deployment info” section of the General tab in the Xcode target editor.

 
 For your containing app, set the deployment target to be the oldest version of iOS that you want to support.

 
 In your containing app, conditionalize calls to the dlopen command within a runtime check for the iOS version by using the systemVersion method.

 
 Call the dlopen command only if your containing app is running in iOS 8.0 or later. Be sure to use Objective-C, not Swift, when making this call.

 
 

 
 Certain iOS APIs use embedded frameworks via the dlopen command. You must conditionalize your use of these APIs just as you do when calling dlopen directly. These APIs are from the CFBundleRef opaque type:

 
 
 CFBundleGetFunctionPointerForName 

 
 CFBundleGetFunctionPointersforNames 

 
 And from the NSBundle class:

 
 
 load 

 
 loadAndReturnError: 

 
 classNamed: 

 
 In a containing app you are deploying to versions of iOS older than 8.0, call these APIs only within a runtime check that ensures you are running in iOS 8.0 or newer, and call these APIs using Objective-C. 

 
 

 
 

 
 
 Creating an App Extension 

 Action 

 Copyright © 2018 Apple Inc. All rights reserved. 
 Terms of Use | 
 Privacy Policy | 
 Updated: 2017-10-19 

 
 

 
 
 
 
 
 
 

 
 
 
 

 

 
 
 
 
 
 
 
 
 Sending feedback…

 
 
 
 We’re sorry, an error has occurred.

 Please try submitting your feedback later.

 
 
 
 Thank you for providing feedback!

 Your input helps improve our developer documentation.

 
 
 
 
 
 How helpful is this document?
 
 * 

 
 
 
 Very helpful
 
 
 
 Somewhat helpful
 
 
 
 Not helpful
 
 
 
 
 How can we improve this document?

 
 
 
 Fix typos or links
 
 
 
 Fix incorrect information
 
 
 
 Add or update code samples
 
 
 
 Add or update illustrations
 
 
 
 Add information about...
 
 
 

 
 * 

 
 * Required information 
 
 

 

 
 
 To submit a product bug or enhancement request, please visit the 
 Bug Reporter 
 page.
 

 
 Please read Apple's Unsolicited Idea Submission Policy 
 before you send us your feedback.
