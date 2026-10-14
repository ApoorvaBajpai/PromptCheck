import { api, Project } from "./api";

export async function loadExampleProject(): Promise<Project> {
  // 1. Create project
  const project = await api.createProject({
    name: "Customer Support QA Bot",
    description:
      "Continuous evaluation suite for Acme Commerce AI customer support agent with regression detection.",
  });

  // 2. Create prompt
  const initialContent = `You are a polite, professional customer support agent for Acme Commerce.
Customer Name: {{ customer_name }}
Order ID: {{ order_id }}
Customer Issue: {{ issue_description }}

Instructions:
1. Greet the customer warmly by their name.
2. Reference their order ID directly.
3. Provide a helpful, clear, and reassuring resolution or update.
4. Conclude with a warm closing statement.`;

  const prompt = await api.createPrompt(project.id, {
    name: "Customer Support Agent",
    description: "Main conversational response generator for incoming support tickets.",
    initial_version_content: initialContent,
    commit_message: "v1.0.0: Initial support agent prompt template",
  });

  // 3. Create 10 comprehensive test cases with all 7 evaluator types
  const sampleTestCases = [
    {
      name: "Late Delivery Inquiry - Alice",
      inputs: {
        customer_name: "Alice Johnson",
        order_id: "ORD-94812",
        issue_description: "My package was expected yesterday but hasn't arrived.",
      },
      expected_output: "Hello Alice Johnson, regarding your order ORD-94812...",
      assertions: [
        { type: "contains", substrings: ["Alice Johnson", "ORD-94812"], mode: "all" },
        { type: "length", min_length: 30, max_length: 500, unit: "characters" },
        { type: "regex", pattern: "ORD-\\d{5}" },
      ],
    },
    {
      name: "Damaged Item on Arrival - Bob",
      inputs: {
        customer_name: "Bob Smith",
        order_id: "ORD-10293",
        issue_description: "The ceramic mug arrived completely shattered.",
      },
      expected_output: "Hello Bob Smith, I am so sorry to hear your order ORD-10293 was damaged...",
      assertions: [
        { type: "contains", substrings: ["Bob Smith", "ORD-10293"], mode: "all" },
        {
          type: "semantic",
          reference_text: "Hello Bob Smith, I sincerely apologize for the broken ceramic mug. We will issue a replacement or refund for order ORD-10293 right away.",
          threshold: 0.75,
        },
      ],
    },
    {
      name: "Address Change Request - Carlos",
      inputs: {
        customer_name: "Carlos Mendez",
        order_id: "ORD-33910",
        issue_description: "I entered the wrong shipping address, please change it before shipping.",
      },
      assertions: [
        { type: "contains", substring: "Carlos Mendez" },
        { type: "contains", substring: "ORD-33910" },
        {
          type: "llm_judge",
          rubric: "Ensure the response addresses updating the shipping address for order ORD-33910 politely and clearly.",
          model: "gemini-2.5-flash",
        },
      ],
    },
    {
      name: "Refund Status Check - Diana",
      inputs: {
        customer_name: "Diana Prince",
        order_id: "ORD-77124",
        issue_description: "I returned the shoes a week ago, when will my refund be posted?",
      },
      assertions: [
        { type: "contains", substring: "Diana" },
        { type: "contains", substring: "refund" },
        { type: "length", min_length: 20, max_length: 600, unit: "characters" },
      ],
    },
    {
      name: "Wrong Item Received - Evan",
      inputs: {
        customer_name: "Evan Wright",
        order_id: "ORD-55201",
        issue_description: "I ordered blue sneakers size 10, but received red boots size 8.",
      },
      assertions: [
        { type: "contains", substrings: ["Evan Wright", "ORD-55201"], mode: "all" },
        { type: "regex", pattern: "(ORD-55201|apolog|exchange|replace)" },
      ],
    },
    {
      name: "Discount Code Not Applied - Fiona",
      inputs: {
        customer_name: "Fiona Gallagher",
        order_id: "ORD-12845",
        issue_description: "My 20% promotional code SAVE20 did not apply to checkout.",
      },
      assertions: [
        { type: "contains", substring: "Fiona" },
        { type: "contains", substring: "ORD-12845" },
        { type: "length", min_length: 20, max_length: 450, unit: "characters" },
      ],
    },
    {
      name: "Subscription Cancellation - George",
      inputs: {
        customer_name: "George Miller",
        order_id: "ORD-66712",
        issue_description: "Please cancel my monthly coffee beans subscription.",
      },
      assertions: [
        { type: "contains", substring: "George Miller" },
        { type: "contains", substring: "subscription" },
      ],
    },
    {
      name: "International Shipping Inquiry - Hannah",
      inputs: {
        customer_name: "Hannah Abbott",
        order_id: "ORD-88190",
        issue_description: "Are customs duties included in order ORD-88190 to the UK?",
      },
      assertions: [
        { type: "contains", substring: "Hannah" },
        { type: "contains", substring: "ORD-88190" },
        { type: "length", min_length: 20, max_length: 500, unit: "characters" },
      ],
    },
    {
      name: "Warranty Claim - Ian",
      inputs: {
        customer_name: "Ian Malcolm",
        order_id: "ORD-44912",
        issue_description: "The blender stopped working after 3 weeks of normal use.",
      },
      assertions: [
        { type: "contains", substring: "Ian" },
        { type: "contains", substring: "ORD-44912" },
        {
          type: "llm_judge",
          rubric: "Ensure the response offers a warranty replacement or troubleshooting steps politely.",
          model: "gemini-2.5-flash",
        },
      ],
    },
    {
      name: "Gift Receipt Request - Julia",
      inputs: {
        customer_name: "Julia Roberts",
        order_id: "ORD-99318",
        issue_description: "Can you email me a gift receipt with prices hidden for ORD-99318?",
      },
      assertions: [
        { type: "contains", substring: "Julia" },
        { type: "contains", substring: "ORD-99318" },
        { type: "contains", mode: "none", substrings: ["credit card", "password"] },
      ],
    },
  ];

  await api.batchImportTestCases(project.id, sampleTestCases);

  return project;
}
