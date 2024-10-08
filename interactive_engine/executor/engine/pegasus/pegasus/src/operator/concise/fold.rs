use std::fmt::Debug;

use crate::api::function::FnResult;
use crate::api::{Fold, Unary};
use crate::communication::output::OutputProxy;
use crate::stream::{Single, SingleItem, Stream};
use crate::tag::tools::map::TidyTagMap;
use crate::{BuildJobError, Data};

impl<D: Data> Fold<D> for Stream<D> {
    fn fold<B, F, C>(self, init: B, factory: C) -> Result<SingleItem<B>, BuildJobError>
    where
        B: Clone + Send + Sync + Debug + 'static,
        F: FnMut(B, D) -> FnResult<B> + Send + 'static,
        C: Fn() -> F + Send + 'static,
    {
        let worker = self.get_worker_id().index;
        let total_peers = self.get_worker_id().total_peers();
        let s = self.aggregate().unary("fold", |info| {
            let mut table = TidyTagMap::<(B, F)>::new(info.scope_level);
            move |input, output| {
                input.for_each_batch(|batch| {
                    if !batch.is_empty() {
                        let (mut accum, mut f) = table
                            .remove(&batch.tag)
                            .unwrap_or((init.clone(), factory()));

                        for d in batch.drain() {
                            accum = f(accum, d)?;
                        }

                        if let Some(end) = batch.take_end() {
                            let mut session = output.new_session(&batch.tag)?;
                            trace_worker!("fold all data and emit result of {:?} ;", batch.tag);
                            session.give_last(Single(accum), end)?;
                        } else {
                            table.insert(batch.tag.clone(), (accum, f));
                        }
                        return Ok(());
                    }

                    if let Some(end) = batch.take_end() {
                        if let Some((accum, _)) = table.remove(&batch.tag) {
                            let mut session = output.new_session(&batch.tag)?;
                            session.give_last(Single(accum), end)?;
                        } else {
                            // decide if it need to output a default value when upstream is empty;
                            // but only one default value should be output;
                            if (end.tag.is_root() && worker == 0)
                                || (!end.tag.is_root() && end.contains_source(worker, total_peers))
                            {
                                let mut session = output.new_session(&batch.tag)?;
                                session.give_last(Single(init.clone()), end)?
                            } else {
                                output.notify_end(end)?;
                            }
                        }
                    }
                    Ok(())
                })
            }
        })?;
        Ok(SingleItem::new(s))
    }

    fn fold_partition<B, F, C>(self, init: B, factory: C) -> Result<SingleItem<B>, BuildJobError>
    where
        B: Clone + Send + Sync + Debug + 'static,
        F: FnMut(B, D) -> FnResult<B> + Send + 'static,
        C: Fn() -> F + Send + 'static,
    {
        let worker = self.get_worker_id().index;
        let total_peers = self.get_worker_id().total_peers();
        let s = self.unary("fold_partition", |info| {
            let mut table = TidyTagMap::<(B, F)>::new(info.scope_level);
            move |input, output| {
                input.for_each_batch(|batch| {
                    if !batch.is_empty() {
                        let (mut accum, mut f) = table
                            .remove(&batch.tag)
                            .unwrap_or((init.clone(), factory()));

                        for d in batch.drain() {
                            accum = f(accum, d)?;
                        }
                        table.insert(batch.tag.clone(), (accum, f));
                    }

                    if let Some(end) = batch.take_end() {
                        if let Some((accum, _)) = table.remove(&batch.tag) {
                            let mut session = output.new_session(&batch.tag)?;
                            session.give_last(Single(accum), end)?;
                        } else {
                            if end.tag.is_root()
                                || (!end.tag.is_root() && end.contains_source(worker, total_peers))
                            {
                                let mut session = output.new_session(&batch.tag)?;
                                session.give_last(Single(init.clone()), end)?
                            } else {
                                output.notify_end(end)?;
                            }
                        }
                    }
                    Ok(())
                })
            }
        })?;
        Ok(SingleItem::new(s))
    }
}
