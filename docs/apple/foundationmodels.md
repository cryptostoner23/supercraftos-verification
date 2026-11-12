<!-- Apple official documentation. Source of truth. -->
<!-- url: https://developer.apple.com/tutorials/data/documentation/foundationmodels.json -->
<!-- fetched: 2026-10-20T00:52:58+00:00 -->
<!-- sha256: 5bbb1726f7df1d27fd6bb2cf23f17a6d62e9b1ea0b36b9175a8efeea48fdf89e -->
<!-- title: Foundation Models -->

# Foundation Models

Official page: <https://developer.apple.com/documentation/foundationmodels>

mentionsdoc://com.apple.foundationmodels/documentation/FoundationModels/updating-prompts-for-new-model-versionsOverview
The Foundation Models framework provides access to any large language model, like the on-device and Private Cloud Compute models designed for Apple Intelligence. These models help you perform intelligent tasks specific to your use case.

foundation-models-framework-heroimage

On-device models excel at a diverse range of text generation tasks, like summarization, entity extraction, text and image understanding, refinement, dialog for games, generating creative content, and more. When you need more reasoning capabilities and context size, use Private Cloud Compute or any server model provider.

The dynamic profile API provides the flexibility to select the best model configuration for your task, and lets you build many useful abstractions, such as agents or skills.

Generate entire Swift data structures with guided generation. With the @Generable macro, you can define custom data structures and the framework provides strong guarantees that the model generates instances of your type.

Use doc://com.apple.foundationmodels/documentation/FoundationModels/Tool to create custom tools that the model can call to assist with handling your request. For example, the model can call a tool that searches a local or online database for information, or calls a service in your app.

To use Apple Foundation Models, people need a device that supports Apple Intelligence. For a list of supported devices, see https://www.apple.com/apple-intelligence/.

What’s new
doc://com.apple.foundationmodels/documentation/FoundationModels/adding-server-side-intelligence-with-private-cloud-computedoc://com.apple.foundationmodels/documentation/FoundationModels/composing-dynamic-sessions-with-instructions-and-profilesdoc://com.apple.foundationmodels/documentation/FoundationModels/analyzing-images-with-multimodal-promptingdoc://com.apple.documentation/videos/play/wwdc2026/242doc://com.apple.documentation/videos/play/wwdc2026/339doc://com.apple.documentation/videos/play/wwdc2026/243compactGridlinkscontent
## Essentials
- doc://com.apple.documentation/documentation/Updates/FoundationModels
- doc://com.apple.foundationmodels/documentation/FoundationModels/generating-content-and-performing-tasks-with-foundation-models
- doc://com.apple.foundationmodels/documentation/FoundationModels/adding-intelligent-app-features-with-generative-models

## Sessions and prompts
- doc://com.apple.foundationmodels/documentation/FoundationModels/prompting-an-on-device-foundation-model
- doc://com.apple.foundationmodels/documentation/FoundationModels/managing-the-context-window
- doc://com.apple.foundationmodels/documentation/FoundationModels/updating-prompts-for-new-model-versions
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelSession
- doc://com.apple.foundationmodels/documentation/FoundationModels/Instructions
- doc://com.apple.foundationmodels/documentation/FoundationModels/Prompt
- doc://com.apple.foundationmodels/documentation/FoundationModels/GenerationOptions
- doc://com.apple.foundationmodels/documentation/FoundationModels/ContextOptions

## Session transcripts
- doc://com.apple.foundationmodels/documentation/FoundationModels/transcripts

## Prompt attachments
- doc://com.apple.foundationmodels/documentation/FoundationModels/analyzing-images-with-multimodal-prompting
- doc://com.apple.foundationmodels/documentation/FoundationModels/Attachment
- doc://com.apple.foundationmodels/documentation/FoundationModels/ImageAttachmentContent
- doc://com.apple.foundationmodels/documentation/FoundationModels/ImageReference

## Dynamic profiles
- doc://com.apple.foundationmodels/documentation/FoundationModels/composing-dynamic-sessions-with-instructions-and-profiles
- doc://com.apple.foundationmodels/documentation/FoundationModels/origami-crafting-a-dynamic-tutorial-for-apple-intelligence
- doc://com.apple.foundationmodels/documentation/FoundationModels/DynamicInstructions
- doc://com.apple.foundationmodels/documentation/FoundationModels/DynamicInstructionsForEach
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelSession/DynamicProfile
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelSession/DynamicProfileModifier
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelSession/Profile

## Structured output
- doc://com.apple.foundationmodels/documentation/FoundationModels/generating-swift-data-structures-with-guided-generation
- doc://com.apple.foundationmodels/documentation/FoundationModels/Generable(description:)
- doc://com.apple.foundationmodels/documentation/FoundationModels/Guide(description:)
- doc://com.apple.foundationmodels/documentation/FoundationModels/Generable
- doc://com.apple.foundationmodels/documentation/FoundationModels/GenerationSchema
- doc://com.apple.foundationmodels/documentation/FoundationModels/DynamicGenerationSchema
- doc://com.apple.foundationmodels/documentation/FoundationModels/GeneratedContent
- doc://com.apple.foundationmodels/documentation/FoundationModels/ConvertibleToGeneratedContent
- doc://com.apple.foundationmodels/documentation/FoundationModels/ConvertibleFromGeneratedContent

## Tools
- doc://com.apple.foundationmodels/documentation/FoundationModels/expanding-generation-with-tool-calling
- doc://com.apple.foundationmodels/documentation/FoundationModels/generate-dynamic-game-content-with-guided-generation-and-tools
- doc://com.apple.foundationmodels/documentation/FoundationModels/Tool

## System language model
- doc://com.apple.foundationmodels/documentation/FoundationModels/supporting-languages-and-locales-with-foundation-models
- doc://com.apple.foundationmodels/documentation/FoundationModels/categorizing-and-organizing-data-with-content-tags
- doc://com.apple.foundationmodels/documentation/FoundationModels/SystemLanguageModel
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelError

## Private Cloud Compute
- doc://com.apple.foundationmodels/documentation/FoundationModels/adding-server-side-intelligence-with-private-cloud-compute
- doc://com.apple.documentation/documentation/BundleResources/Entitlements/com.apple.developer.private-cloud-compute
- doc://com.apple.foundationmodels/documentation/FoundationModels/PrivateCloudComputeLanguageModel

## Custom language model provider
- doc://com.apple.foundationmodels/documentation/FoundationModels/running-a-core-ai-model-in-a-foundation-models-session
- doc://com.apple.foundationmodels/documentation/FoundationModels/optimizing-key-value-caching-in-language-model-sessions
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModel
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelCapabilities
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelExecutor
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelExecutorGenerationChannel
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelExecutorGenerationRequest

## Custom session properties
- doc://com.apple.foundationmodels/documentation/FoundationModels/LanguageModelSession/SessionProperty
- doc://com.apple.foundationmodels/documentation/FoundationModels/SessionPropertyKey
- doc://com.apple.foundationmodels/documentation/FoundationModels/SessionPropertyValues
- doc://com.apple.foundationmodels/documentation/FoundationModels/SessionPropertyEntry()

## Safety
- doc://com.apple.foundationmodels/documentation/FoundationModels/improving-the-safety-of-generative-model-output

## Performance and evaluation
- doc://com.apple.foundationmodels/documentation/FoundationModels/evaluating-prompts-to-measure-performance-and-improve-model-responses
- doc://com.apple.documentation/documentation/Evaluations/evaluating-language-model-responses
- doc://com.apple.foundationmodels/documentation/FoundationModels/analyzing-the-runtime-performance-of-your-foundation-models-app

## Protocols
- doc://com.apple.foundationmodels/documentation/FoundationModels/DataAttachmentRepresentable
- doc://com.apple.foundationmodels/documentation/FoundationModels/DataEntryRepresentable
