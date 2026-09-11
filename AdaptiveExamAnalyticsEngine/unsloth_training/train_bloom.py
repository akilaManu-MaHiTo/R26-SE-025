"""Fine-tune Qwen3-8B for the engine's QuestionSemantics JSON contract.

Designed for a CUDA-enabled Google Colab runtime. Run ``--help`` locally
without installing Unsloth; GPU dependencies are imported only after the
dataset passes validation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from validate_dataset import DatasetValidationError, validate_paths


ROOT = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=ROOT / "data" / "example_train.jsonl")
    parser.add_argument(
        "--validation",
        type=Path,
        default=ROOT / "data" / "example_validation.jsonl",
    )
    parser.add_argument("--model", default="unsloth/Qwen3-8B-bnb-4bit")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "qwen3-bloom-lora")
    parser.add_argument("--gguf-dir", type=Path, default=ROOT / "outputs" / "qwen3-bloom-gguf")
    parser.add_argument("--export-gguf", action="store_true")
    parser.add_argument("--allow-example-data", action="store_true")
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--seed", type=int, default=3407)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = validate_paths(
            [args.train, args.validation],
            require_adjudicated=not args.allow_example_data,
        )
    except DatasetValidationError as exc:
        print(f"Dataset validation failed before model loading:\n{exc}")
        return 1
    print(f"Validated dataset: {summary}")

    import torch
    from datasets import load_dataset
    from trl import SFTConfig, SFTTrainer
    from unsloth import FastLanguageModel

    if not torch.cuda.is_available():
        raise RuntimeError("A CUDA GPU runtime is required. In Colab choose Runtime > T4 GPU.")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_length,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
        use_rslora=False,
        loftq_config=None,
    )

    dataset = load_dataset(
        "json",
        data_files={"train": str(args.train), "validation": str(args.validation)},
    )

    def format_messages(batch):
        return {
            "text": [
                tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=False,
                )
                for messages in batch["messages"]
            ]
        }

    dataset = dataset.map(format_messages, batched=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        args=SFTConfig(
            output_dir=str(args.output_dir),
            dataset_text_field="text",
            max_seq_length=args.max_seq_length,
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=args.gradient_accumulation,
            num_train_epochs=args.epochs,
            learning_rate=args.learning_rate,
            warmup_ratio=0.1,
            logging_steps=1,
            eval_strategy="epoch",
            save_strategy="epoch",
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=args.seed,
            report_to="none",
            packing=False,
        ),
    )
    trainer.train()

    model.save_pretrained(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    print(f"Saved LoRA adapter to {args.output_dir}")

    if args.export_gguf:
        args.gguf_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained_gguf(
            str(args.gguf_dir),
            tokenizer,
            quantization_method="q4_k_m",
        )
        print(f"Saved q4_k_m GGUF to {args.gguf_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
