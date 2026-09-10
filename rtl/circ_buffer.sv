// Circular capture buffer. Writes until post-trigger fill, then freeze.
// Crossing sample is last pre-trigger (already written when trigger arrives).
module circ_buffer #(
    parameter int DEPTH       = 2048,
    parameter int WIDTH       = 12,
    parameter int PRE_TRIGGER = 512
) (
    input  logic                     clk,
    input  logic                     rst,
    input  logic                     clear,
    input  logic                     wr_en,
    input  logic [WIDTH-1:0]         wr_data,
    input  logic                     trigger,
    output logic                     frozen,
    output logic                     pre_filled,
    output logic [$clog2(DEPTH)-1:0] oldest_addr,
    input  logic [$clog2(DEPTH)-1:0] rd_addr,
    output logic [WIDTH-1:0]         rd_data
);

    localparam int AW   = $clog2(DEPTH);
    localparam int CW   = AW + 1;
    localparam int POST = DEPTH - PRE_TRIGGER;

    logic [WIDTH-1:0] mem [0:DEPTH-1];
    logic [AW-1:0]    wr_ptr;
    logic [CW-1:0]    pre_cnt;
    logic [CW-1:0]    post_cnt;
    logic             post_fill;

    always_ff @(posedge clk) begin
        if (wr_en && !frozen)
            mem[wr_ptr] <= wr_data;
        rd_data <= mem[rd_addr];
    end

    always_ff @(posedge clk) begin
        if (rst || clear) begin
            frozen      <= 1'b0;
            pre_filled  <= 1'b0;
            oldest_addr <= '0;
            wr_ptr      <= '0;
            pre_cnt     <= '0;
            post_cnt    <= '0;
            post_fill   <= 1'b0;
        end else begin
            if (trigger && pre_filled && !frozen && !post_fill)
                post_fill <= 1'b1;

            if (wr_en && !frozen) begin
                if (wr_ptr == (DEPTH - 1))
                    wr_ptr <= '0;
                else
                    wr_ptr <= wr_ptr + 1'b1;

                if (!pre_filled) begin
                    if (pre_cnt == (PRE_TRIGGER - 1))
                        pre_filled <= 1'b1;
                    else
                        pre_cnt <= pre_cnt + 1'b1;
                end

                if (post_fill) begin
                    if (post_cnt == (POST - 1)) begin
                        frozen <= 1'b1;
                        if (wr_ptr == (DEPTH - 1))
                            oldest_addr <= '0;
                        else
                            oldest_addr <= wr_ptr + 1'b1;
                    end else begin
                        post_cnt <= post_cnt + 1'b1;
                    end
                end
            end
        end
    end

endmodule
