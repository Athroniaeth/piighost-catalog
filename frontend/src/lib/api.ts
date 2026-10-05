/**
 * Thin wrappers over the generated SDK.
 *
 * The generated names carry the operation id, which reads badly at the call
 * site (`apiV1RefsNamespaceSelectorResolvedResolved`). These wrappers give each
 * one a short name, unwrap the envelope, and turn an error response into a
 * thrown `ApiError` so a page can `await` and catch.
 */

import {
  apiV1CompareCompare,
  apiV1LabelsLabels,
  apiV1GroupsPreviewPreview,
  apiV1PlaygroundCandidateCandidate,
  apiV1PlaygroundChatChat,
  apiV1PlaygroundPlayground,
  apiV1RefsNamespaceManifestManifest,
  apiV1RefsNamespaceObjectDetail,
  apiV1RefsNamespaceSelectorCommitDetail,
  apiV1RefsNamespaceSelectorPipelineTomlPipelineToml,
  apiV1RefsNamespaceSelectorResolvedResolved,
  apiV1RefsNamespaceSelectorSnippetsSnippetsFor,
  apiV1SamplesSamples,
  apiV1SearchSearch,
  apiV1StatsStats,
  apiV1SubmissionsCheckSubmission,
  apiV1VocabularyVocabulary,
} from "../generated/api";
import type {
  ChatOut,
  CommitDetail,
  CompareOut,
  LabelsOut,
  ManifestOut,
  ObjectDetail,
  PreviewOut,
  Resolved,
  RunOut,
  SamplesOut,
  SearchOut,
  SnippetsOut,
  StatsOut,
  SubmissionResult,
  VocabularyOut,
} from "../generated/api";

import { t } from "./i18n.svelte";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * The generated client marks `response` optional, because a transport failure
 * produces no response at all. The envelope mirrors that rather than asserting
 * it away, so a network error surfaces as an ApiError like any other.
 */
type Envelope<T> = { data?: T; error?: unknown; response?: Response };

function unwrap<T>(result: Envelope<T>): T {
  if (result.data !== undefined && result.response?.ok) return result.data;
  const detail =
    typeof result.error === "object" &&
    result.error !== null &&
    "detail" in result.error
      ? String((result.error as { detail: unknown }).detail)
      : result.response?.statusText || t("common.unreachable");
  throw new ApiError(detail, result.response?.status ?? 0);
}

export type Ref = { namespace: string; name: string; selector: string };

export const api = {
  async search(params: {
    q?: string;
    kind?: ("pattern" | "group" | "config")[];
    tag?: string[];
    label?: string;
    sort?: "relevance" | "updated" | "used" | "labels" | "pulls" | "name";
  }): Promise<SearchOut> {
    return unwrap(await apiV1SearchSearch({ query: params }));
  },

  async vocabulary(): Promise<VocabularyOut> {
    return unwrap(await apiV1VocabularyVocabulary());
  },

  async labels(): Promise<LabelsOut> {
    return unwrap(await apiV1LabelsLabels());
  },

  async stats(days: number): Promise<StatsOut> {
    return unwrap(await apiV1StatsStats({ query: { days } }));
  },

  async samples(): Promise<SamplesOut> {
    return unwrap(await apiV1SamplesSamples());
  },

  async object(namespace: string, name: string): Promise<ObjectDetail> {
    return unwrap(
      await apiV1RefsNamespaceObjectDetail({ path: { namespace, name } }),
    );
  },

  async manifest(namespace: string, name: string): Promise<ManifestOut> {
    return unwrap(
      await apiV1RefsNamespaceManifestManifest({ path: { namespace, name } }),
    );
  },

  async commit(ref: Ref): Promise<CommitDetail> {
    return unwrap(await apiV1RefsNamespaceSelectorCommitDetail({ path: ref }));
  },

  async resolved(ref: Ref): Promise<Resolved> {
    return unwrap(
      await apiV1RefsNamespaceSelectorResolvedResolved({ path: ref }),
    );
  },

  async snippets(ref: Ref): Promise<SnippetsOut> {
    return unwrap(
      await apiV1RefsNamespaceSelectorSnippetsSnippetsFor({ path: ref }),
    );
  },

  async pipeline(
    ref: Ref,
    options: {
      memory?: "in_memory" | "redis" | "sqlalchemy";
      keepRefs?: boolean;
      part?: "pipeline" | "detector";
    } = {},
  ): Promise<string> {
    const result = await apiV1RefsNamespaceSelectorPipelineTomlPipelineToml({
      path: ref,
      query: {
        memory: options.memory,
        keep_refs: options.keepRefs,
        part: options.part,
      },
      parseAs: "text",
    });
    return unwrap(result as unknown as Envelope<string>);
  },

  async run(ref: string, text: string): Promise<RunOut> {
    return unwrap(await apiV1PlaygroundPlayground({ body: { ref, text } }));
  },

  async candidate(regex: string, text: string, label: string): Promise<RunOut> {
    return unwrap(
      await apiV1PlaygroundCandidateCandidate({ body: { regex, text, label } }),
    );
  },

  async chat(ref: string, messages: string[]): Promise<ChatOut> {
    return unwrap(await apiV1PlaygroundChatChat({ body: { ref, messages } }));
  },

  async preview(
    sources: { ref: string; exclude: string[] }[],
  ): Promise<PreviewOut> {
    return unwrap(await apiV1GroupsPreviewPreview({ body: { sources } }));
  },

  async compare(refs: string[], text: string): Promise<CompareOut> {
    return unwrap(await apiV1CompareCompare({ body: { refs, text } }));
  },

  async submit(payload: {
    kind: string;
    namespace: string;
    name: string;
    manifest: string;
  }): Promise<SubmissionResult> {
    return unwrap(await apiV1SubmissionsCheckSubmission({ body: payload }));
  },
};

/** Download a string as a file, without a round trip to the server. */
export function download(filename: string, body: string, type: string) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
