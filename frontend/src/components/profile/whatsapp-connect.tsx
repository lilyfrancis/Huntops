import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, MessageCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { whatsappApi } from "@/lib/api";

/*
  Saving a number is not the same as being reachable, and the gap between the
  two is invisible without this.

  A WhatsApp message a business sends first has to be an approved template, and
  the daily digest is classified as marketing — Meta reviewed it and refused
  Utility, on the grounds that "you have 3 new matches" invites someone back
  rather than reporting a transaction. Marketing templates are dropped for
  anyone who has never messaged the business, and dropped silently: the API
  answers 200, the message never lands, and nothing anywhere says so.

  So the person has to message us once. This explains that in the one place
  they have just typed their number, and takes the guesswork out of it by
  pre-filling the message.
*/
export function WhatsAppConnect() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["whatsapp", "connection"],
    queryFn: whatsappApi.connection,
    retry: false,
  });

  // Nothing useful to say while it loads, and nothing at all to say if the
  // operator has not set WhatsApp up — an explanation of a feature that does
  // not exist here is just noise on the page.
  if (isLoading || !data?.configured) return null;

  if (!data.number_on_file) {
    return (
      <p className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-ink-muted">
        Save a number above, then connect it — WhatsApp will not deliver to you until you have
        messaged us once.
      </p>
    );
  }

  if (data.opted_in) {
    return (
      <p className="flex items-center gap-2 rounded-lg border border-good/30 bg-good-soft px-3 py-2 text-xs text-good">
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        WhatsApp is connected. Your digest can reach {data.number_on_file}.
      </p>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-warning/30 bg-warning-soft px-3 py-3">
      <p className="text-xs leading-relaxed text-warning">
        <strong className="font-semibold">One step left.</strong> WhatsApp only lets us message
        you after you have messaged us. Until then your digest is sent and silently dropped — you
        would never see it, and neither would we.
      </p>
      {data.opt_in_url && (
        <div className="flex flex-wrap items-center gap-2">
          <Button asChild size="sm">
            <a href={data.opt_in_url} target="_blank" rel="noreferrer">
              <MessageCircle className="h-4 w-4" />
              Connect WhatsApp
            </a>
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => queryClient.invalidateQueries({ queryKey: ["whatsapp", "connection"] })}
          >
            <RefreshCw className="h-4 w-4" />
            I have sent it
          </Button>
        </div>
      )}
      <p className="text-[0.7rem] text-warning/80">
        Opens WhatsApp with the message ready. Send it, then tap “I have sent it”.
      </p>
    </div>
  );
}
