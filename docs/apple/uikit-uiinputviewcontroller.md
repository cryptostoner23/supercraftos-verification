<!-- Apple official documentation. Source of truth. -->
<!-- url: https://developer.apple.com/tutorials/data/documentation/uikit/uiinputviewcontroller.json -->
<!-- fetched: 2026-10-20T00:52:55+00:00 -->
<!-- sha256: 9999b76775a6aa962949bc65f4d1f6d89642aedb8385b7d66a3b64faedaf58d0 -->
<!-- title: UIInputViewController -->

# UIInputViewController

Official page: <https://developer.apple.com/documentation/uikit/uiinputviewcontroller>

swiftiOSiPadOSMac CatalysttvOSvisionOSattribute@doc://com.apple.documentation/documentation/Swift/MainActorattributes:ScMMainActortext keywordclasstext identifierUIInputViewControllerdeclarationsmentionsdoc://com.apple.uikit/documentation/UIKit/configuring-open-access-for-a-custom-keyboarddoc://com.apple.uikit/documentation/UIKit/handling-text-interactions-in-custom-keyboardsOverview
To create a custom keyboard, first subclass the doc://com.apple.uikit/documentation/UIKit/UIInputViewController class, then add your keyboard’s user interface to the doc://com.apple.uikit/documentation/UIKit/UIInputViewController/inputView property of your subclass. In Xcode, you can start a custom keyboard by choosing the Custom Keyboard target template.

A custom keyboard can respond to user input events in the following ways:

Add text in the form of an unattributed doc://com.apple.documentation/documentation/Foundation/NSString object at the insertion point in the current text input object, by calling the doc://com.apple.uikit/documentation/UIKit/UIKeyInput/insertText(_:) method on the doc://com.apple.uikit/documentation/UIKit/UIInputViewController/textDocumentProxy property. This property provides that method through its conformance to the doc://com.apple.uikit/documentation/UIKit/UIKeyInput protocol

Delete text in a backward direction, starting at the insertion point, by calling the doc://com.apple.uikit/documentation/UIKit/UIKeyInput/deleteBackward() method on the doc://com.apple.uikit/documentation/UIKit/UIInputViewController/textDocumentProxy property.

Switch to another keyboard in the set of user-enabled keyboards, by calling the doc://com.apple.uikit/documentation/UIKit/UIInputViewController/advanceToNextInputMode() method.

Dismiss the keyboard, by calling the doc://com.apple.uikit/documentation/UIKit/UIInputViewController/dismissKeyboard() method.

Obtain textual context around the insertion point by reading the doc://com.apple.uikit/documentation/UIKit/UIInputViewController/textDocumentProxy properties doc://com.apple.uikit/documentation/UIKit/UITextDocumentProxy/documentContextBeforeInput and doc://com.apple.uikit/documentation/UIKit/UITextDocumentProxy/documentContextAfterInput. To find out if the current text input object is empty, call the doc://com.apple.uikit/documentation/UIKit/UIKeyInput/hasText method on the doc://com.apple.uikit/documentation/UIKit/UIInputViewController/textDocumentProxy property. You can employ this textual context by considering it along with user input, to offer context-sensitive output to a document from your keyboard.

An input view controller conforms to the doc://com.apple.uikit/documentation/UIKit/UITextInputDelegate protocol, allowing you to respond to changes in document content and position of the insertion point.

To present an appropriate keyboard layout, respond to the current text input object’s doc://com.apple.uikit/documentation/UIKit/UIKeyboardType property. For each keyboard type trait you support, change the contents of your primary view accordingly.

For more about creating a custom keyboard, read https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/CustomKeyboard.html#//apple_ref/doc/uid/TP40014214-CH16 in https://developer.apple.com/library/archive/documentation/General/Conceptual/ExtensibilityPG/index.html#//apple_ref/doc/uid/TP40014214.

content
## Providing a user interface for a custom keyboard
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/inputView

## Controlling a custom keyboard
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/advanceToNextInputMode()
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/dismissKeyboard()
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/handleInputModeList(from:with:)

## Interacting with a text input object
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/textDocumentProxy
- doc://com.apple.uikit/documentation/UIKit/UITextDocumentProxy

## Obtaining a supplementary lexicon
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/requestSupplementaryLexicon(completion:)

## Changing the primary language of a custom keyboard
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/primaryLanguage

## Configuring the keyboard behaviors
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/needsInputModeSwitchKey
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/hasFullAccess
- doc://com.apple.uikit/documentation/UIKit/UIInputViewController/hasDictationKey
