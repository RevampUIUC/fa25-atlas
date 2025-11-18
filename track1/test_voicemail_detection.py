"""
Test script for voicemail detection accuracy metrics

This script tests the voicemail detection system with various scenarios
and provides accuracy metrics.
"""

import sys
from datetime import datetime
from app.voicemail_detector import VoicemailDetector


# Test cases with expected outcomes
TEST_CASES = [
    {
        "name": "Clear AMD Detection - Machine with Beep",
        "call_sid": "TEST001",
        "answered_by": "machine_end_beep",
        "transcripts": None,
        "call_duration": 25,
        "expected": True,
        "confidence_threshold": 0.9
    },
    {
        "name": "Clear AMD Detection - Human",
        "call_sid": "TEST002",
        "answered_by": "human",
        "transcripts": None,
        "call_duration": 120,
        "expected": False,
        "confidence_threshold": 0.0
    },
    {
        "name": "Keyword Detection - Leave a Message",
        "call_sid": "TEST003",
        "answered_by": None,
        "transcripts": [
            {
                "speaker": "system",
                "text": "Hello, you have reached John Doe. Please leave a message after the beep.",
                "ts": datetime.utcnow(),
                "confidence": 0.98,
                "start_offset": 0.0,
                "is_final": True
            }
        ],
        "call_duration": 20,
        "expected": True,
        "confidence_threshold": 0.7
    },
    {
        "name": "Keyword Detection - Not Available",
        "call_sid": "TEST004",
        "answered_by": None,
        "transcripts": [
            {
                "speaker": "system",
                "text": "I'm not available right now. Leave your message at the tone.",
                "ts": datetime.utcnow(),
                "confidence": 0.97,
                "start_offset": 0.5,
                "is_final": True
            }
        ],
        "call_duration": 18,
        "expected": True,
        "confidence_threshold": 0.7
    },
    {
        "name": "Human Conversation",
        "call_sid": "TEST005",
        "answered_by": "human",
        "transcripts": [
            {
                "speaker": "agent",
                "text": "Hello, how can I help you today?",
                "ts": datetime.utcnow(),
                "confidence": 0.95,
                "start_offset": 1.5,
                "is_final": True
            },
            {
                "speaker": "caller",
                "text": "Hi, I need help with my account.",
                "ts": datetime.utcnow(),
                "confidence": 0.94,
                "start_offset": 5.0,
                "is_final": True
            }
        ],
        "call_duration": 180,
        "expected": False,
        "confidence_threshold": 0.0
    },
    {
        "name": "Combined Signals - AMD + Keywords",
        "call_sid": "TEST006",
        "answered_by": "machine_end_silence",
        "transcripts": [
            {
                "speaker": "system",
                "text": "You've reached the voicemail of Jane Smith. Please record your message.",
                "ts": datetime.utcnow(),
                "confidence": 0.99,
                "start_offset": 0.0,
                "is_final": True
            }
        ],
        "call_duration": 22,
        "expected": True,
        "confidence_threshold": 0.9
    },
    {
        "name": "Professional Voicemail - Out of Office",
        "call_sid": "TEST007",
        "answered_by": "machine_start",
        "transcripts": [
            {
                "speaker": "system",
                "text": "I'm currently out of the office. Please leave a message and I'll return your call.",
                "ts": datetime.utcnow(),
                "confidence": 0.98,
                "start_offset": 0.2,
                "is_final": True
            }
        ],
        "call_duration": 25,
        "expected": True,
        "confidence_threshold": 0.85
    },
    {
        "name": "Carrier Voicemail Message",
        "call_sid": "TEST008",
        "answered_by": "machine_end_other",
        "transcripts": [
            {
                "speaker": "system",
                "text": "The person you are calling is not available. Please leave a message after the tone.",
                "ts": datetime.utcnow(),
                "confidence": 0.99,
                "start_offset": 0.0,
                "is_final": True
            }
        ],
        "call_duration": 20,
        "expected": True,
        "confidence_threshold": 0.8
    },
    {
        "name": "Ambiguous - Short Call, No AMD",
        "call_sid": "TEST009",
        "answered_by": None,
        "transcripts": [
            {
                "speaker": "unknown",
                "text": "Hello",
                "ts": datetime.utcnow(),
                "confidence": 0.90,
                "start_offset": 2.0,
                "is_final": True
            }
        ],
        "call_duration": 8,
        "expected": False,  # Uncertain - should not trigger false positive
        "confidence_threshold": 0.0
    },
    {
        "name": "Pattern Analysis - Monologue with High Confidence",
        "call_sid": "TEST010",
        "answered_by": None,
        "transcripts": [
            {
                "speaker": "system",
                "text": "Thank you for calling.",
                "ts": datetime.utcnow(),
                "confidence": 0.99,
                "start_offset": 0.5,
                "is_final": True
            },
            {
                "speaker": "system",
                "text": "Your call is important to us.",
                "ts": datetime.utcnow(),
                "confidence": 0.99,
                "start_offset": 3.0,
                "is_final": True
            },
            {
                "speaker": "system",
                "text": "If you'd like to leave a message, please do so now.",
                "ts": datetime.utcnow(),
                "confidence": 0.98,
                "start_offset": 7.0,
                "is_final": True
            }
        ],
        "call_duration": 30,
        "expected": True,
        "confidence_threshold": 0.7
    }
]


def run_test(detector: VoicemailDetector, test_case: dict) -> dict:
    """Run a single test case"""
    result = detector.analyze_call(
        call_sid=test_case["call_sid"],
        answered_by=test_case["answered_by"],
        transcripts=test_case["transcripts"],
        call_duration=test_case["call_duration"],
        metadata={}
    )

    passed = (
        result.is_voicemail == test_case["expected"] and
        (not test_case["expected"] or result.confidence >= test_case["confidence_threshold"])
    )

    return {
        "name": test_case["name"],
        "call_sid": test_case["call_sid"],
        "expected": test_case["expected"],
        "detected": result.is_voicemail,
        "confidence": result.confidence,
        "method": result.detection_method,
        "signals": len(result.signals),
        "passed": passed,
        "result": result
    }


def calculate_metrics(results: list) -> dict:
    """Calculate accuracy metrics"""
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    # Confusion matrix
    true_positives = sum(1 for r in results if r["expected"] and r["detected"])
    true_negatives = sum(1 for r in results if not r["expected"] and not r["detected"])
    false_positives = sum(1 for r in results if not r["expected"] and r["detected"])
    false_negatives = sum(1 for r in results if r["expected"] and not r["detected"])

    # Metrics
    accuracy = passed / total if total > 0 else 0
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "total_tests": total,
        "passed": passed,
        "failed": failed,
        "accuracy": accuracy,
        "confusion_matrix": {
            "true_positives": true_positives,
            "true_negatives": true_negatives,
            "false_positives": false_positives,
            "false_negatives": false_negatives
        },
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score
    }


def print_results(results: list, metrics: dict):
    """Print test results and metrics"""
    print("\n" + "=" * 80)
    print("VOICEMAIL DETECTION TEST RESULTS")
    print("=" * 80 + "\n")

    # Individual test results
    print("Individual Test Results:")
    print("-" * 80)
    for i, result in enumerate(results, 1):
        status = "[PASS]" if result["passed"] else "[FAIL]"
        print(f"\n{i}. {result['name']} - {status}")
        print(f"   Call SID: {result['call_sid']}")
        print(f"   Expected: {'Voicemail' if result['expected'] else 'Human'}")
        print(f"   Detected: {'Voicemail' if result['detected'] else 'Human'}")
        print(f"   Confidence: {result['confidence']:.2%}")
        print(f"   Method: {result['method']}")
        print(f"   Signals: {result['signals']}")

    # Summary metrics
    print("\n" + "=" * 80)
    print("SUMMARY METRICS")
    print("=" * 80 + "\n")

    print(f"Total Tests: {metrics['total_tests']}")
    print(f"Passed: {metrics['passed']} ({metrics['passed']/metrics['total_tests']:.1%})")
    print(f"Failed: {metrics['failed']} ({metrics['failed']/metrics['total_tests']:.1%})")
    print(f"\nAccuracy: {metrics['accuracy']:.2%}")
    print(f"Precision: {metrics['precision']:.2%}")
    print(f"Recall: {metrics['recall']:.2%}")
    print(f"F1 Score: {metrics['f1_score']:.2%}")

    print("\nConfusion Matrix:")
    cm = metrics['confusion_matrix']
    print(f"  True Positives:  {cm['true_positives']}")
    print(f"  True Negatives:  {cm['true_negatives']}")
    print(f"  False Positives: {cm['false_positives']}")
    print(f"  False Negatives: {cm['false_negatives']}")

    # Method distribution
    method_counts = {}
    for result in results:
        method = result['method']
        method_counts[method] = method_counts.get(method, 0) + 1

    print("\nDetection Methods Used:")
    for method, count in sorted(method_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {method}: {count}")

    print("\n" + "=" * 80 + "\n")


def main():
    """Main test runner"""
    print("Initializing Voicemail Detector...")

    # Test with default configuration
    detector = VoicemailDetector(
        amd_confidence_threshold=0.85,
        keyword_confidence_threshold=0.75,
        min_signals_required=1,
        enable_aggressive_detection=False
    )

    print(f"Running {len(TEST_CASES)} test cases...\n")

    # Run all tests
    results = []
    for test_case in TEST_CASES:
        result = run_test(detector, test_case)
        results.append(result)

    # Calculate metrics
    metrics = calculate_metrics(results)

    # Print results
    print_results(results, metrics)

    # Get detector statistics
    stats = detector.get_statistics()
    print("Detector Statistics:")
    print(f"  Total Analyzed: {stats['total_analyzed']}")
    print(f"  Voicemail Rate: {stats.get('voicemail_rate', 0):.1%}")
    print(f"  Human Rate: {stats.get('human_rate', 0):.1%}")
    print(f"  Uncertain Rate: {stats.get('uncertain_rate', 0):.1%}")

    # Return exit code based on pass/fail
    return 0 if metrics['failed'] == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
