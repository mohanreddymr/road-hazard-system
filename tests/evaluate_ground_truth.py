"""
evaluate_ground_truth.py
━━━━━━━━━━━━━━━━━━━━
Compare a prediction CSV against ground truth labels.

Usage:
    python tests/evaluate_ground_truth.py output/session_YYYYMMDD_HHMMSS.csv
    python tests/evaluate_ground_truth.py output/session_YYYYMMDD_HHMMSS.csv ground_truth.csv

The prediction CSV may already include a 'ground_truth' column.
If not, provide a separate ground truth CSV file.
"""

import csv
import os
import sys
from collections import defaultdict

EVENT_TO_DECISION = {
    'POTHOLE': 'HAZARD',
    'CRACK': 'HAZARD',
    'SPEED_HUMP': 'CAUTION',
    'BRAKING': 'CAUTION',
    'SPEED HUMP': 'CAUTION',
    'NORMAL': 'NORMAL',
    'CAUTION': 'CAUTION',
    'HAZARD': 'HAZARD',
}


def normalize_label(value):
    if value is None:
        return None
    label = str(value).strip().upper()
    return EVENT_TO_DECISION.get(label, label)


def read_ground_truth_file(path):
    labels = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames and 'ground_truth' in [name.strip().lower() for name in reader.fieldnames]:
            for row in reader:
                labels.append(normalize_label(row.get('ground_truth', '')))
            return labels

        f.seek(0)
        reader = csv.reader(f)
        for row in reader:
            if row:
                labels.append(normalize_label(row[0]))
    return labels


def read_predictions(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError('Prediction file has no header')
        for row in reader:
            rows.append(row)
    if not rows:
        raise ValueError('Prediction file is empty')
    return rows


def compute_confusion(actual_list, predicted_list):
    matrix = defaultdict(int)
    labels = set()
    for actual, predicted in zip(actual_list, predicted_list):
        matrix[(actual, predicted)] += 1
        labels.add(actual)
        labels.add(predicted)
    labels = sorted(label for label in labels if label is not None)
    return matrix, labels


def render_confusion(matrix, labels):
    header = 'Actual \ Pred'.ljust(15) + ''.join(label.rjust(12) for label in labels)
    lines = [header]
    for actual in labels:
        row = actual.ljust(15)
        for predicted in labels:
            row += str(matrix.get((actual, predicted), 0)).rjust(12)
        lines.append(row)
    return '\n'.join(lines)


def print_and_save_report(predicted_path, total, correct, incorrect, accuracy, matrix_text):
    summary_lines = [
        'GROUND TRUTH EVALUATION REPORT',
        '========================================',
        f'Predictions processed : {total}',
        f'Correct predictions   : {correct}',
        f'Incorrect predictions : {incorrect}',
        f'Accuracy             : {accuracy:.1f}%',
        '',
        matrix_text,
    ]
    report_text = '\n'.join(summary_lines)
    print(report_text)

    out_path = os.path.splitext(predicted_path)[0] + '_evaluation.txt'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f'\nSaved evaluation report to: {out_path}')


def main():
    if len(sys.argv) < 2:
        print('Usage: python tests/evaluate_ground_truth.py <predictions.csv> [ground_truth.csv]')
        sys.exit(1)

    predictions_csv = sys.argv[1]
    truth_csv = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(predictions_csv):
        print(f'Prediction file not found: {predictions_csv}')
        sys.exit(1)

    rows = read_predictions(predictions_csv)
    predicted = []
    actual = []

    for row in rows:
        decision = normalize_label(row.get('decision', ''))
        predicted.append(decision)
        if 'ground_truth' in row and row.get('ground_truth', '').strip():
            actual.append(normalize_label(row['ground_truth']))
        else:
            actual.append(None)

    if truth_csv:
        if not os.path.exists(truth_csv):
            print(f'Ground truth file not found: {truth_csv}')
            sys.exit(1)
        actual = read_ground_truth_file(truth_csv)

    if any(value is None for value in actual):
        print('Error: missing ground truth labels for some predictions.')
        print('Provide a prediction CSV with a ground_truth column or a separate ground truth CSV.')
        sys.exit(1)

    if len(predicted) != len(actual):
        print('Warning: prediction count and ground truth count differ.')
        min_len = min(len(predicted), len(actual))
        predicted = predicted[:min_len]
        actual = actual[:min_len]

    total = len(predicted)
    correct = sum(1 for p, a in zip(predicted, actual) if p == a)
    incorrect = total - correct
    accuracy = (correct / total * 100) if total else 0.0

    matrix, labels = compute_confusion(actual, predicted)
    matrix_text = render_confusion(matrix, labels)

    print_and_save_report(predictions_csv, total, correct, incorrect, accuracy, matrix_text)


if __name__ == '__main__':
    main()
