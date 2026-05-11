import torch
import torchaudio
import json
import os
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2Processor
import numpy as np

def extract_speech_emotion(audio_path, model_name="ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"):
    """Extract speech emotion features using Wav2Vec2 from HuggingFace Transformers"""
    print(f"Loading emotion recognition model: {model_name}")
    
    # Load processor and model
    processor = Wav2Vec2Processor.from_pretrained(model_name)
    model = Wav2Vec2ForSequenceClassification.from_pretrained(model_name)
    
    # Set model to evaluation mode
    model.eval()
    
    print(f"Processing audio file: {audio_path}")
    
    # Load audio
    signal, fs = torchaudio.load(audio_path)
    
    # Ensure mono audio
    if signal.shape[0] > 1:
        signal = torch.mean(signal, dim=0, keepdim=True)
    
    # Resample if necessary (model expects 16kHz)
    if fs != 16000:
        resampler = torchaudio.transforms.Resample(fs, 16000)
        signal = resampler(signal)
    
    # Process audio
    print("Processing audio for emotion recognition...")
    inputs = processor(signal.squeeze().numpy(), sampling_rate=16000, return_tensors="pt", padding=True)
    
    # Get predictions
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
    
    # Get probabilities
    probabilities = torch.nn.functional.softmax(logits, dim=-1)
    probs_list = probabilities.squeeze().tolist()
    
    # Get predicted class
    predicted_class = torch.argmax(probabilities, dim=-1).item()
    confidence = probs_list[predicted_class]
    
    # Get emotion labels from model config
    emotion_labels = list(model.config.id2label.values())
    
    # Create emotion features dictionary
    emotion_features = {
        "predicted_emotion": emotion_labels[predicted_class],
        "emotion_index": predicted_class,
        "emotion_probabilities": dict(zip(emotion_labels, probs_list)),
        "confidence": float(confidence)
    }
    
    print(f"Predicted emotion: {emotion_labels[predicted_class]} (confidence: {confidence:.3f})")
    print("Emotion probabilities:")
    for label, prob in zip(emotion_labels, probs_list):
        print(f"  {label}: {prob:.3f}")
    
    return emotion_features

if __name__ == "__main__":
    audio_path = "audio.wav"
    if os.path.exists(audio_path):
        emotion_features = extract_speech_emotion(audio_path)
        
        # Save emotion features to JSON
        with open("emotion_features.json", "w", encoding="utf-8") as f:
            json.dump(emotion_features, f, indent=2)
        
        print(f"\nEmotion features saved to emotion_features.json")
    else:
        print(f"Audio file not found: {audio_path}")
        print("Please run extract_audio.py first")