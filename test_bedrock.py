#!/usr/bin/env python3
"""
Debug script to test AWS Bedrock connectivity using the actual BedrockProvider class.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the actual provider
from core.bedrock_provider import BedrockProvider

def test_bedrock_provider():
    """Test the BedrockProvider class"""
    print("="*70)
    print("Testing BedrockProvider Class")
    print("="*70)
    
    # Get environment variables
    model_id = os.getenv("ANTHROPIC_MODEL")
    aws_profile = os.getenv("AWS_PROFILE")
    aws_region = os.getenv("AWS_REGION")
    
    print(f"ANTHROPIC_MODEL: {model_id}")
    print(f"AWS_PROFILE: {aws_profile}")
    print(f"AWS_REGION: {aws_region}")
    print()
    
    try:
        # Create provider instance
        print("Creating BedrockProvider instance...")
        provider = BedrockProvider()
        print(f"✓ Provider created")
        print(f"  Model ID: {provider.model_id}")
        print(f"  Region: {provider.region}")
        print(f"  Profile: {provider.profile_name}")
        print()
        
        # Get model
        print("Getting LLM model...")
        llm = provider.get_model()
        print(f"✓ Model retrieved")
        print(f"  Model type: {type(llm).__name__}")
        print()
        
        # Test with a simple prompt
        print("Testing with simple prompt...")
        response = llm.invoke("Say 'Hello from ADAG!' in one sentence.")
        print(f"✓ SUCCESS!")
        print(f"Response: {response.content}")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ FAILED!")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_with_structured_output():
    """Test with structured output (like the intake agent uses)"""
    print("\n" + "="*70)
    print("Testing with Structured Output (Intake Agent Pattern)")
    print("="*70)
    
    from pydantic import BaseModel
    from typing import List
    
    class TestResponse(BaseModel):
        message: str
        success: bool
    
    try:
        # Create provider and get model
        provider = BedrockProvider()
        llm = provider.get_model()
        
        # Use structured output
        print("Creating structured LLM...")
        structured_llm = llm.with_structured_output(TestResponse)
        print("✓ Structured LLM created")
        print()
        
        # Test invocation
        print("Invoking with structured output...")
        result = structured_llm.invoke(
            "Return a JSON with message='Hello from structured output' and success=true"
        )
        print(f"✓ SUCCESS!")
        print(f"Result: {result}")
        print(f"  Message: {result.message}")
        print(f"  Success: {result.success}")
        print()
        
        return True
        
    except Exception as e:
        print(f"✗ FAILED!")
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function"""
    print("\n" + "="*70)
    print("ADAG Bedrock Provider Test")
    print("="*70)
    print()
    
    # Test 1: Basic provider test
    test1_passed = test_bedrock_provider()
    
    # Test 2: Structured output test (like intake agent)
    test2_passed = test_with_structured_output()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Basic Provider Test: {'✓ PASSED' if test1_passed else '✗ FAILED'}")
    print(f"Structured Output Test: {'✓ PASSED' if test2_passed else '✗ FAILED'}")
    print()
    
    if test1_passed and test2_passed:
        print("✓ All tests passed! The provider is working correctly.")
        sys.exit(0)
    else:
        print("✗ Some tests failed. Check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
